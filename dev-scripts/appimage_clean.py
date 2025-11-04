#!/usr/bin/env python3
"""
PySide6 Dependencies Analyzer with ldd support
Анализирует зависимости PySide6 модулей используя ldd для определения
реальных зависимостей скомпилированных библиотек.
"""

import ast
import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Set, Dict, List
import argparse
import json


class PySide6DependencyAnalyzer:
    def __init__(self, project_root: Path = None):
        # Системные библиотеки, которые нужно всегда оставлять
        self.system_libs = {
            'libQt6XcbQpa', 'libQt6Wayland', 'libQt6Egl',
            'libicudata', 'libicuuc', 'libicui18n', 'libQt6DBus'
        }

        self.real_dependencies = {}
        self.used_modules_code = set()
        self.used_modules_ldd = set()
        self.all_required_modules = set()
        
        # Определяем корень проекта
        if project_root is None:
            # Корень проекта - две директории выше от скрипта
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = project_root
            
        self.venv_path = self.project_root / ".venv"
        self.build_path = self.project_root / "build-aux"

    def find_python_files(self, directory: Path) -> List[Path]:
        """Находит все Python файлы в директории"""
        python_files = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git'}]

            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        return python_files

    def find_pyside6_libs(self, base_path: Path) -> Dict[str, Path]:
        """Находит все PySide6 библиотеки (.so файлы)"""
        libs = {}

        # Ищем venv в корне проекта
        venv_candidates = [
            self.venv_path,  # .venv
            self.project_root / "venv",
            self.project_root / ".virtualenv",
        ]
        
        pyside6_path = None
        
        # Пробуем найти PySide6 в venv
        for venv in venv_candidates:
            if venv.exists():
                # Ищем Python версию
                lib_path = venv / "lib"
                if lib_path.exists():
                    for python_dir in lib_path.iterdir():
                        if python_dir.name.startswith('python'):
                            candidate = python_dir / "site-packages" / "PySide6"
                            if candidate.exists():
                                pyside6_path = candidate
                                print(f"Найден PySide6 в: {candidate}")
                                break
                    if pyside6_path:
                        break
        
        if not pyside6_path:
            print(f"Предупреждение: PySide6 не найден в venv, проверяем AppDir...")
            # Если не нашли в venv, пробуем в AppDir
            if base_path:
                appdir_candidate = base_path / "AppDir/usr/local/lib"
                if appdir_candidate.exists():
                    for python_dir in appdir_candidate.iterdir():
                        if python_dir.name.startswith('python'):
                            candidate = python_dir / "dist-packages" / "PySide6"
                            if candidate.exists():
                                pyside6_path = candidate
                                print(f"Найден PySide6 в AppDir: {candidate}")
                                break

        if not pyside6_path:
            return libs

        # Ищем .so файлы модулей
        for so_file in pyside6_path.glob("Qt*.*.so"):
            module_name = so_file.stem.split('.')[0]  # QtCore.abi3.so -> QtCore
            if module_name.startswith('Qt'):
                libs[module_name] = so_file

        # Также ищем в подпапках
        for subdir in pyside6_path.iterdir():
            if subdir.is_dir() and subdir.name.startswith('Qt'):
                for so_file in subdir.glob("*.so*"):
                    if 'Qt' in so_file.name:
                        libs[subdir.name] = so_file
                        break

        return libs

    def analyze_ldd_dependencies(self, lib_path: Path) -> Set[str]:
        """Анализирует зависимости библиотеки с помощью ldd"""
        qt_deps = set()

        try:
            result = subprocess.run(['ldd', str(lib_path)],
                                  capture_output=True, text=True, check=True)

            # Парсим вывод ldd и ищем Qt библиотеки
            for line in result.stdout.split('\n'):
                # Ищем строки вида: libQt6Core.so.6 => /path/to/lib
                match = re.search(r'libQt6(\w+)\.so', line)
                if match:
                    qt_module = f"Qt{match.group(1)}"
                    qt_deps.add(qt_module)

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Предупреждение: не удалось выполнить ldd для {lib_path}: {e}")

        return qt_deps

    def build_real_dependency_graph(self, pyside_libs: Dict[str, Path]) -> Dict[str, Set[str]]:
        """Строит граф зависимостей на основе ldd анализа"""
        dependencies = {}

        print("Анализ реальных зависимостей с помощью ldd...")
        for module, lib_path in pyside_libs.items():
            print(f"  Анализируется {module}...")
            deps = self.analyze_ldd_dependencies(lib_path)
            dependencies[module] = deps

            if deps:
                print(f"    Зависимости: {', '.join(sorted(deps))}")

        return dependencies

    def analyze_file_imports(self, file_path: Path) -> Set[str]:
        """Анализирует один Python файл и возвращает используемые PySide6 модули"""
        modules = set()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('PySide6.'):
                            module = alias.name.split('.', 2)[1]
                            if module.startswith('Qt'):
                                modules.add(module)

                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('PySide6.'):
                        module = node.module.split('.', 2)[1]
                        if module.startswith('Qt'):
                            modules.add(module)

        except Exception as e:
            print(f"Ошибка при анализе {file_path}: {e}")

        return modules

    def get_all_dependencies(self, modules: Set[str], dependency_graph: Dict[str, Set[str]]) -> Set[str]:
        """Получает все зависимости для набора модулей, используя граф зависимостей из ldd"""
        all_deps = set(modules)

        if not dependency_graph:
            return all_deps

        # Повторяем до тех пор, пока не найдем все транзитивные зависимости
        changed = True
        iteration = 0
        while changed and iteration < 10:  # Защита от бесконечного цикла
            changed = False
            current_deps = set(all_deps)

            for module in current_deps:
                if module in dependency_graph:
                    new_deps = dependency_graph[module] - all_deps
                    if new_deps:
                        all_deps.update(new_deps)
                        changed = True

            iteration += 1

        return all_deps

    def analyze_project(self, project_path: Path, appdir_path: Path = None) -> Dict:
        """Анализирует весь проект"""
        python_files = self.find_python_files(project_path)
        print(f"Найдено {len(python_files)} Python файлов")

        # Анализ статических импортов
        used_modules_code = set()
        file_modules = {}

        for file_path in python_files:
            modules = self.analyze_file_imports(file_path)
            if modules:
                file_modules[str(file_path.relative_to(project_path))] = list(modules)
                used_modules_code.update(modules)

        print(f"Найдено {len(used_modules_code)} модулей в коде: {', '.join(sorted(used_modules_code))}")

        # Поиск PySide6 библиотек
        search_base = appdir_path if appdir_path else project_path
        pyside_libs = self.find_pyside6_libs(search_base)

        if not pyside_libs:
            print("ОШИБКА: PySide6 библиотеки не найдены! Анализ невозможен.")
            return {
                'error': 'PySide6 библиотеки не найдены',
                'analysis_method': 'failed',
                'found_libraries': 0,
                'directly_used_code': sorted(used_modules_code),
                'all_required': [],
                'removable': [],
                'available_modules': [],
                'file_usage': file_modules
            }

        print(f"Найдено {len(pyside_libs)} PySide6 библиотек")

        # Анализ реальных зависимостей с ldd
        real_dependencies = self.build_real_dependency_graph(pyside_libs)

        # Определяем модули, которые реально используются через ldd
        used_modules_ldd = set()
        for module in used_modules_code:
            if module in real_dependencies:
                used_modules_ldd.update(real_dependencies[module])
                used_modules_ldd.add(module)

        print(f"Реальные зависимости через ldd: {', '.join(sorted(used_modules_ldd))}")

        # Объединяем результаты анализа кода и ldd
        all_used_modules = used_modules_code | used_modules_ldd

        # Получаем все необходимые модули включая зависимости
        all_required = self.get_all_dependencies(all_used_modules, real_dependencies)

        # Все доступные PySide6 модули
        available_modules = set(pyside_libs.keys())

        # Модули, которые можно удалить
        removable = available_modules - all_required

        return {
            'analysis_method': 'ldd + static analysis',
            'found_libraries': len(pyside_libs),
            'directly_used_code': sorted(used_modules_code),
            'directly_used_ldd': sorted(used_modules_ldd),
            'all_required': sorted(all_required),
            'removable': sorted(removable),
            'available_modules': sorted(available_modules),
            'file_usage': file_modules,
            'real_dependencies': {k: sorted(v) for k, v in real_dependencies.items()},
            'library_paths': {k: str(v) for k, v in pyside_libs.items()},
            'analysis_summary': {
                'total_modules': len(available_modules),
                'required_modules': len(all_required),
                'removable_modules': len(removable),
                'space_saving_potential': f"{len(removable)/len(available_modules)*100:.1f}%" if available_modules else "0%"
            }
        }

    def generate_appimage_recipe(self, removable_modules: List[str], template_path: Path) -> str:
        """Генерирует обновленный AppImage рецепт с командами очистки"""

        # Читаем существующий рецепт
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                recipe_content = f.read()
        except FileNotFoundError:
            print(f"Шаблон рецепта не найден: {template_path}")
            return ""

        # Генерируем новые команды очистки
        cleanup_lines = []

        # QML удаляем только если не используется
        qml_modules = {'QtQml', 'QtQuick', 'QtQuickWidgets'}
        if qml_modules.issubset(set(removable_modules)):
            cleanup_lines.append("  - rm -rf AppDir/usr/local/lib/python3.10/dist-packages/PySide6/Qt/qml/")

        # Инструменты разработки (всегда удаляем)
        cleanup_lines.append("  - rm -f AppDir/usr/local/lib/python3.10/dist-packages/PySide6/{assistant,designer,linguist,lrelease,lupdate}")

        # Модули для удаления
        if removable_modules:
            modules_list = ','.join([f"{mod}*" for mod in sorted(removable_modules)])
            cleanup_lines.append(f"  - rm -f AppDir/usr/local/lib/python3.10/dist-packages/PySide6/{{{modules_list}}}")

        # Генерируем команду для удаления нативных библиотек с сохранением нужных
        required_libs = set()
        for module in sorted(set(self.all_required_modules)):
            required_libs.add(f"libQt6{module.replace('Qt', '')}*")

        # Добавляем системные библиотеки
        for lib in self.system_libs:
            required_libs.add(f"{lib}*")

        keep_pattern = '|'.join(sorted(required_libs))

        cleanup_lines.extend([
            "  - shopt -s extglob",
            f"  - rm -rf AppDir/usr/local/lib/python3.10/dist-packages/PySide6/Qt/lib/!({keep_pattern})"
        ])

        import re
        
        # Ищем весь блок команд очистки PySide6 (от первой rm до AppDir:)
        # Паттерн: после "  - cp -r lib AppDir/usr\n" идут команды rm, а затем "AppDir:"
        pattern = r'(  - cp -r lib AppDir/usr\n)((?:  - (?:rm|shopt).*\n)*?)(?=AppDir:)'
        
        match = re.search(pattern, recipe_content)
        
        if not match:
            print("ПРЕДУПРЕЖДЕНИЕ: Не удалось найти блок очистки в рецепте")
            print("Добавляем команды очистки перед блоком AppDir:")
            
            # Просто вставим команды перед AppDir:
            appdir_pos = recipe_content.find('AppDir:')
            if appdir_pos != -1:
                new_content = (
                    recipe_content[:appdir_pos] + 
                    '\n'.join(cleanup_lines) + '\n' +
                    recipe_content[appdir_pos:]
                )
                return new_content
            else:
                print("ОШИБКА: Не найден блок AppDir: в рецепте")
                return ""
        
        # Создаем замену - группа 1 (cp -r lib) + новые команды очистки
        replacement = r'\1' + '\n'.join(cleanup_lines) + '\n'
        
        updated_recipe = re.sub(pattern, replacement, recipe_content, count=1)

        return updated_recipe


def main():
    parser = argparse.ArgumentParser(description='Анализ зависимостей PySide6 модулей с использованием ldd')
    parser.add_argument('project_path', nargs='?', default='.',
                        help='Путь к проекту для анализа (по умолчанию: текущая директория)')
    parser.add_argument('--appdir', help='Путь к AppDir для поиска PySide6 библиотек')
    parser.add_argument('--output', '-o', help='Путь для сохранения результатов (JSON)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    parser.add_argument('--venv', help='Путь к виртуальному окружению (по умолчанию: .venv в корне проекта)')

    args = parser.parse_args()

    project_path = Path(args.project_path).resolve()
    if not project_path.exists():
        print(f"Ошибка: путь {project_path} не существует")
        sys.exit(1)

    appdir_path = Path(args.appdir).resolve() if args.appdir else None
    if appdir_path and not appdir_path.exists():
        print(f"Предупреждение: AppDir путь {appdir_path} не существует")
        appdir_path = None

    # Определяем корень проекта
    # Если запущен из подпапки проекта, ищем корень
    project_root = project_path
    if (project_path / ".git").exists() or (project_path / "pyproject.toml").exists():
        project_root = project_path
    else:
        # Пытаемся найти корень проекта
        current = project_path
        while current != current.parent:
            if (current / ".git").exists() or (current / "pyproject.toml").exists():
                project_root = current
                break
            current = current.parent
    
    print(f"Корень проекта: {project_root}")

    analyzer = PySide6DependencyAnalyzer(project_root=project_root)
    
    # Если указан custom venv путь
    if args.venv:
        analyzer.venv_path = Path(args.venv).resolve()
        print(f"Использую указанный venv: {analyzer.venv_path}")
    
    results = analyzer.analyze_project(project_path, appdir_path)

    # Сохраняем в анализатор для генерации команд
    analyzer.all_required_modules = set(results.get('all_required', []))

    # Выводим результаты
    print("\n" + "="*60)
    print("АНАЛИЗ ЗАВИСИМОСТЕЙ PYSIDE6 (ldd analysis)")
    print("="*60)

    if 'error' in results:
        print(f"\nОШИБКА: {results['error']}")
        sys.exit(1)

    print(f"\nМетод анализа: {results['analysis_method']}")
    print(f"Найдено библиотек: {results['found_libraries']}")

    if results['directly_used_code']:
        print(f"\nИспользуемые модули в коде ({len(results['directly_used_code'])}):")
        for module in results['directly_used_code']:
            print(f"  • {module}")

    if results['directly_used_ldd']:
        print(f"\nРеальные зависимости через ldd ({len(results['directly_used_ldd'])}):")
        for module in results['directly_used_ldd']:
            print(f"  • {module}")

    print(f"\nВсе необходимые модули ({len(results['all_required'])}):")
    for module in results['all_required']:
        print(f"  • {module}")

    print(f"\nМодули, которые можно удалить ({len(results['removable'])}):")
    for module in results['removable']:
        print(f"  • {module}")

    print(f"\nПотенциальная экономия места: {results['analysis_summary']['space_saving_potential']}")

    if args.verbose and results['real_dependencies']:
        print(f"\nРеальные зависимости (ldd):")
        for module, deps in results['real_dependencies'].items():
            if deps:
                print(f"  {module} → {', '.join(deps)}")

    # Обновляем AppImage рецепт
    recipe_path = analyzer.build_path / "AppImageBuilder.yml"
    if recipe_path.exists():
        updated_recipe = analyzer.generate_appimage_recipe(results['removable'], recipe_path)
        if updated_recipe:
            with open(recipe_path, 'w', encoding='utf-8') as f:
                f.write(updated_recipe)
            print(f"\nAppImage рецепт обновлен: {recipe_path}")
        else:
            print(f"\nОШИБКА: не удалось обновить рецепт")
    else:
        print(f"\nПредупреждение: рецепт AppImage не найден в {recipe_path}")

    # Сохраняем результаты в JSON
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Результаты сохранены в: {args.output}")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
