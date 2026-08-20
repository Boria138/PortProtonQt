from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QPushButton, QScrollArea, QSlider, QWidget

from portprotonqt.input_manager.mixin import InputMixin


class SettingsVisualNavigationMixin(InputMixin):
    def _get_mangohud_nav_sections(self):
        """Return settings tool focusable widgets grouped by visual sections."""
        if not self.settings_dialog:
            return []
        current_tab = self.settings_dialog.tab_widget.currentWidget()
        is_mangohud = current_tab == getattr(self.settings_dialog, "mangohud_tab", None)
        is_vkbasalt = current_tab == getattr(self.settings_dialog, "vkbasalt_tab", None)
        is_gamescope = current_tab == getattr(self.settings_dialog, "gamescope_tab", None)
        if not is_mangohud and not is_vkbasalt and not is_gamescope:
            return []

        sections = []

        value_widgets = []
        if is_mangohud:
            value_widgets = [
                widget for key, widget in self.settings_dialog.mangohud_widgets.items()
                if key != 'fps_limit_method' and widget.isVisible() and widget.isEnabled()
            ]
        elif is_gamescope:
            value_widgets = [
                widget for widget in self.settings_dialog.gamescope_widgets.values()
                if widget.isVisible() and widget.isEnabled()
            ]
            value_widgets.extend([
                widget for widget in self.settings_dialog.gamescope_resolution_widgets.values()
                if widget.isVisible() and widget.isEnabled()
            ])

        mangohud_tab = self.settings_dialog.tab_widget.currentWidget()
        preset_buttons = []
        if mangohud_tab:
            preset_buttons = [
                widget for widget in mangohud_tab.findChildren(
                    QPushButton, options=Qt.FindChildOption.FindChildrenRecursively
                )
                if widget.isVisible() and widget.isEnabled()
            ]
        preset_section = self._sort_widgets_by_position(preset_buttons) if preset_buttons else []

        toggle_widgets = []
        if is_vkbasalt:
            toggle_widgets = [
                checkbox for checkbox in self.settings_dialog.vkbasalt_shader_widgets.values()
                if checkbox.isVisible() and checkbox.isEnabled()
            ]
        else:
            category_combo_attr = 'mangohud_category_combo' if is_mangohud else 'gamescope_category_combo'
            category_stack_attr = 'mangohud_category_stack' if is_mangohud else 'gamescope_category_stack'
            category_combo = getattr(self.settings_dialog, category_combo_attr, None)
            if category_combo and category_combo.isVisible() and category_combo.isEnabled():
                toggle_widgets.append(category_combo)
            category_stack = getattr(self.settings_dialog, category_stack_attr, None)
            if category_stack:
                category_widget = category_stack.currentWidget()
                if category_widget:
                    category_checkboxes = [
                        checkbox for checkbox in category_widget.findChildren(
                            QCheckBox, options=Qt.FindChildOption.FindChildrenRecursively
                        )
                        if checkbox.isVisible() and checkbox.isEnabled()
                    ]
                    toggle_widgets.extend(self._sort_widgets_by_position(category_checkboxes))
        toggle_section = toggle_widgets if toggle_widgets else []

        fps_section = []
        if is_mangohud:
            fps_widgets = []
            fps_limit_method = self.settings_dialog.mangohud_widgets.get('fps_limit_method')
            if fps_limit_method and fps_limit_method.isVisible() and fps_limit_method.isEnabled():
                fps_widgets.append(fps_limit_method)

            fps_widgets.extend([
                checkbox for checkbox in self.settings_dialog.mangohud_fps_widgets.values()
                if checkbox.isVisible() and checkbox.isEnabled()
            ])
            if fps_widgets:
                fps_section = self._sort_widgets_by_position(fps_widgets)

        if is_vkbasalt:
            extra_edit = getattr(self.settings_dialog, 'vkbasalt_cas_slider', None)
        else:
            extra_edit_attr = 'mangohud_extra_edit' if is_mangohud else 'gamescope_extra_edit'
            extra_edit = getattr(self.settings_dialog, extra_edit_attr, None)
        extra_section = [extra_edit] if extra_edit and extra_edit.isVisible() and extra_edit.isEnabled() else []

        if is_mangohud:
            if preset_section:
                sections.append(preset_section)
            if toggle_section:
                sections.append(toggle_section)
            if value_widgets:
                sections.append(self._sort_widgets_by_position(value_widgets))
            if fps_section:
                sections.append(fps_section)
            if extra_section:
                sections.append(extra_section)
        elif is_gamescope:
            # Gamescope UI order: presets -> toggles -> values -> extra.
            if preset_section:
                sections.append(preset_section)
            if toggle_section:
                sections.append(toggle_section)
            if value_widgets:
                sections.append(self._sort_widgets_by_position(value_widgets))
            if extra_section:
                sections.append(extra_section)
        else:
            if preset_section:
                sections.append(preset_section)
            if extra_section:
                sections.append(extra_section)
            if toggle_section:
                sections.append(self._sort_widgets_by_position(toggle_section))

        return sections

    def _sort_widgets_by_position(self, widgets):
        """Sort widgets by their y/x position in settings dialog coordinates."""
        return sorted(
            widgets,
            key=lambda widget: (
                widget.mapTo(self.settings_dialog, widget.rect().topLeft()).y(),
                widget.mapTo(self.settings_dialog, widget.rect().topLeft()).x(),
            ),
        )

    def _find_widget_in_sections(self, widget, sections):
        """Find widget position in sections list."""
        for section_index, section in enumerate(sections):
            for widget_index, item in enumerate(section):
                if item is widget:
                    return section_index, widget_index
        return None

    def _focus_mangohud_widget(self, widget):
        """Focus MangoHud widget and ensure it is visible in scroll area."""
        self._ensure_mangohud_widget_visible(widget)
        widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def _ensure_mangohud_widget_visible(self, widget):
        """Auto-scroll MangoHud tab to the currently focused widget."""
        if not self.settings_dialog:
            return
        mangohud_tab = self.settings_dialog.tab_widget.currentWidget()
        if not mangohud_tab:
            return
        scroll_area = mangohud_tab.findChild(QScrollArea)
        if scroll_area:
            scroll_area.ensureWidgetVisible(widget, 20, 20)

    def _move_mangohud_horizontal(self, focused, direction, sections):
        """Move focus left/right inside current MangoHud section."""
        position = self._find_widget_in_sections(focused, sections)
        if not position:
            return
        if isinstance(focused, QSlider):
            focused.setValue(focused.value() + direction)
            return
        section_index, _widget_index = position
        target = self._find_mangohud_grid_horizontal_target(
            focused, direction, sections[section_index]
        )
        if target:
            self._focus_mangohud_widget(target)
            return
        target = self._find_mangohud_neighbor_in_section(
            focused, sections[section_index], direction, is_vertical=False
        )
        if target:
            self._focus_mangohud_widget(target)

    def _move_mangohud_vertical(self, focused, direction, sections):
        """Move focus up/down inside section, then across sections."""
        position = self._find_widget_in_sections(focused, sections)
        if not position:
            return
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return

        current_tab = settings_dialog.tab_widget.currentWidget()
        is_mangohud = current_tab == getattr(settings_dialog, "mangohud_tab", None)
        is_vkbasalt = current_tab == getattr(settings_dialog, "vkbasalt_tab", None)
        section_index, _widget_index = position
        if is_vkbasalt and isinstance(focused, QSlider) and direction > 0:
            target = self._find_vkbasalt_first_effect_widget()
            if target:
                self._focus_mangohud_widget(target)
                return

        toggle_boundary_reached = False
        if self._is_mangohud_fps_widget(focused):
            fps_target = self._find_mangohud_fps_vertical_target(
                focused, direction, sections[section_index]
            )
            if fps_target:
                self._focus_mangohud_widget(fps_target)
                return
        if self._is_mangohud_toggle_widget(focused):
            toggle_target = self._find_mangohud_toggle_vertical_target(
                focused, direction, sections[section_index]
            )
            if toggle_target:
                self._focus_mangohud_widget(toggle_target)
                return
            toggle_boundary_reached = True

        fps_limit_method = None
        if is_mangohud:
            fps_limit_method = settings_dialog.mangohud_widgets.get('fps_limit_method')
        if direction > 0 and is_mangohud and fps_limit_method and focused is fps_limit_method:
            fps_checkboxes = [
                checkbox for checkbox in settings_dialog.mangohud_fps_widgets.values()
                if checkbox.isVisible() and checkbox.isEnabled()
            ]
            if fps_checkboxes:
                first_fps_checkbox = self._sort_widgets_by_position(fps_checkboxes)[0]
                self._focus_mangohud_widget(first_fps_checkbox)
                return

        category_combo = None
        category_stack = None
        if not is_vkbasalt:
            category_combo_attr = 'mangohud_category_combo' if is_mangohud else 'gamescope_category_combo'
            category_stack_attr = 'mangohud_category_stack' if is_mangohud else 'gamescope_category_stack'
            category_combo = getattr(settings_dialog, category_combo_attr, None)
            category_stack = getattr(settings_dialog, category_stack_attr, None)
        if direction > 0 and category_combo and focused is category_combo and category_stack:
            current_category_widget = category_stack.currentWidget()
            if current_category_widget:
                category_checkboxes = [
                    checkbox for checkbox in current_category_widget.findChildren(
                        QCheckBox, options=Qt.FindChildOption.FindChildrenRecursively
                    )
                    if checkbox.isVisible() and checkbox.isEnabled()
                ]
                if category_checkboxes:
                    first_checkbox = self._sort_widgets_by_position(category_checkboxes)[0]
                    self._focus_mangohud_widget(first_checkbox)
                    return

        if not toggle_boundary_reached:
            target_in_section = self._find_mangohud_neighbor_in_section(
                focused, sections[section_index], direction, is_vertical=True
            )
            if target_in_section:
                self._focus_mangohud_widget(target_in_section)
                return

        target_section_index = section_index + direction
        if target_section_index < 0 or target_section_index >= len(sections):
            return

        target_section = sections[target_section_index]
        if not target_section:
            return

        if category_combo and category_combo in target_section:
            self._focus_mangohud_widget(category_combo)
            return

        if target_section_index == 1:
            self._focus_mangohud_widget(target_section[0])
            return

        fps_limit_method = None
        if is_mangohud:
            fps_limit_method = settings_dialog.mangohud_widgets.get('fps_limit_method')
        if fps_limit_method and fps_limit_method in target_section:
            self._focus_mangohud_widget(fps_limit_method)
            return

        current_center = focused.mapTo(settings_dialog, focused.rect().center()).x()
        target_widget = min(
            target_section,
            key=lambda widget: abs(widget.mapTo(settings_dialog, widget.rect().center()).x() - current_center),
        )
        self._focus_mangohud_widget(target_widget)

    def _find_mangohud_neighbor_in_section(self, focused, section, direction, is_vertical):
        """Find closest focusable neighbor in current section by direction."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        focused_center = focused.mapTo(settings_dialog, focused.rect().center())
        fx = focused_center.x()
        fy = focused_center.y()
        candidates = []

        for widget in section:
            if widget is focused:
                continue
            center = widget.mapTo(settings_dialog, widget.rect().center())
            dx = center.x() - fx
            dy = center.y() - fy

            if is_vertical:
                if direction < 0 and dy >= -4:
                    continue
                if direction > 0 and dy <= 4:
                    continue
                score = abs(dy) + abs(dx) * 3
            else:
                if direction < 0 and dx >= -4:
                    continue
                if direction > 0 and dx <= 4:
                    continue
                score = abs(dx) + abs(dy) * 3

            candidates.append((score, widget))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _find_mangohud_grid_horizontal_target(
        self, focused: QWidget, direction: int, section: list[QWidget]
    ) -> QWidget | None:
        """Navigate left/right in MangoHud grids with row wrap at edges."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        sorted_widgets = sorted(
            section,
            key=lambda widget: (
                widget.mapTo(settings_dialog, widget.rect().center()).y(),
                widget.mapTo(settings_dialog, widget.rect().center()).x(),
            ),
        )
        rows = []
        tolerance = 24
        for widget in sorted_widgets:
            y = widget.mapTo(settings_dialog, widget.rect().center()).y()
            if not rows:
                rows.append([widget])
                continue
            last_y = rows[-1][0].mapTo(settings_dialog, rows[-1][0].rect().center()).y()
            if abs(y - last_y) <= tolerance:
                rows[-1].append(widget)
            else:
                rows.append([widget])
        for row in rows:
            row.sort(key=lambda widget: widget.mapTo(settings_dialog, widget.rect().center()).x())

        row_idx = -1
        col_idx = -1
        for index, row in enumerate(rows):
            if focused in row:
                row_idx = index
                col_idx = row.index(focused)
                break
        if row_idx == -1:
            return None

        if direction > 0:
            if col_idx + 1 < len(rows[row_idx]):
                return rows[row_idx][col_idx + 1]
            if row_idx + 1 < len(rows):
                return rows[row_idx + 1][0]
            return None
        if direction < 0:
            if col_idx - 1 >= 0:
                return rows[row_idx][col_idx - 1]
            if row_idx - 1 >= 0:
                return rows[row_idx - 1][-1]
            return None
        return None

    def _is_mangohud_fps_widget(self, widget):
        """Check if widget belongs to MangoHud FPS section."""
        if not self.settings_dialog:
            return False
        return widget in set(self.settings_dialog.mangohud_fps_widgets.values())

    def _is_mangohud_toggle_widget(self, widget: QWidget) -> bool:
        """Check if widget belongs to MangoHud/Gamescope toggle checkbox section."""
        if not self.settings_dialog:
            return False
        current_tab = self.settings_dialog.tab_widget.currentWidget()
        if current_tab == getattr(self.settings_dialog, "mangohud_tab", None):
            toggle_keys = getattr(self.settings_dialog, 'mangohud_toggle_widget_keys', {})
            return isinstance(widget, QCheckBox) and widget in toggle_keys
        if current_tab == getattr(self.settings_dialog, "vkbasalt_tab", None):
            toggle_widgets = getattr(self.settings_dialog, 'vkbasalt_shader_widgets', {})
            return isinstance(widget, QCheckBox) and widget in set(toggle_widgets.values())
        elif current_tab == getattr(self.settings_dialog, "gamescope_tab", None):
            toggle_keys = getattr(self.settings_dialog, 'gamescope_toggle_widget_keys', {})
        else:
            toggle_keys = {}
        return isinstance(widget, QCheckBox) and widget in toggle_keys

    def _find_mangohud_toggle_vertical_target(
        self, focused: QWidget, direction: int, section: list[QWidget]
    ) -> QWidget | None:
        """Navigate toggle checkboxes down/up with automatic next/prev column jump."""
        toggle_widgets = [widget for widget in section if self._is_mangohud_toggle_widget(widget)]
        if not toggle_widgets:
            return None
        if self._is_current_vkbasalt_tab():
            return self._find_vkbasalt_effect_vertical_target(focused, direction, toggle_widgets)
        return self._find_mangohud_vertical_grid_target(focused, direction, toggle_widgets)

    def _is_current_vkbasalt_tab(self) -> bool:
        if not self.settings_dialog:
            return False
        current_tab = self.settings_dialog.tab_widget.currentWidget()
        return current_tab == getattr(self.settings_dialog, "vkbasalt_tab", None)

    def _find_vkbasalt_first_effect_widget(self) -> QWidget | None:
        if not self.settings_dialog:
            return None
        widgets = [
            widget for widget in self.settings_dialog.vkbasalt_shader_widgets.values()
            if widget.isVisible() and widget.isEnabled()
        ]
        if not widgets:
            return None
        return self._sort_widgets_by_position(widgets)[0]

    def _find_vkbasalt_effect_vertical_target(
        self, focused: QWidget, direction: int, widgets: list[QWidget]
    ) -> QWidget | None:
        if not self.settings_dialog:
            return None
        target = self._find_mangohud_vertical_grid_target(focused, direction, widgets)
        if direction >= 0 or target is None:
            return target
        focused_pos = focused.mapTo(self.settings_dialog, focused.rect().center())
        target_pos = target.mapTo(self.settings_dialog, target.rect().center())
        if target_pos.x() < focused_pos.x() and target_pos.y() > focused_pos.y():
            return None
        return target

    def _find_mangohud_fps_vertical_target(self, focused, direction, section):
        """Navigate FPS widgets down/up with automatic next/prev column jump."""
        fps_widgets = [widget for widget in section if self._is_mangohud_fps_widget(widget)]
        if not fps_widgets:
            return None
        return self._find_mangohud_vertical_grid_target(focused, direction, fps_widgets)

    def _find_mangohud_vertical_grid_target(
        self, focused: QWidget, direction: int, widgets: list[QWidget]
    ) -> QWidget | None:
        """Find a vertical target in grid columns."""
        settings_dialog = self.settings_dialog
        if not settings_dialog:
            return None
        sorted_widgets = sorted(
            widgets,
            key=lambda widget: (
                widget.mapTo(settings_dialog, widget.rect().center()).x(),
                widget.mapTo(settings_dialog, widget.rect().center()).y(),
            ),
        )
        columns = []
        tolerance = 24
        for widget in sorted_widgets:
            x = widget.mapTo(settings_dialog, widget.rect().center()).x()
            if not columns:
                columns.append([widget])
                continue
            last_x = columns[-1][0].mapTo(settings_dialog, columns[-1][0].rect().center()).x()
            if abs(x - last_x) <= tolerance:
                columns[-1].append(widget)
            else:
                columns.append([widget])

        col_idx = -1
        row_idx = -1
        for index, column in enumerate(columns):
            if focused in column:
                col_idx = index
                row_idx = column.index(focused)
                break
        if col_idx == -1:
            return None

        if direction > 0:
            if row_idx + 1 < len(columns[col_idx]):
                return columns[col_idx][row_idx + 1]
            return None

        if direction < 0:
            if row_idx - 1 >= 0:
                return columns[col_idx][row_idx - 1]
            return None
        return None
