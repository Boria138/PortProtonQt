📘  Эта документация также доступна на [русском](README.ru.md)

---

## 📋 Contents
- [Overview](#overview)
- [How It Works](#how-it-works)
  - [Data Priorities](#data-priorities)
  - [File Structure](#file-structure)
- [For Users](#for-users)
  - [Creating User Overrides](#creating-user-overrides)
  - [Example](#example)
- [For Developers](#for-developers)
  - [Adding Built-In Overrides](#adding-built-in-overrides)

---

## 📖 Overview

In `PortProtonQT`, you can change:

- Game title
- Description
- Cover image

Override types:

| Type            | Location                                        | Priority |
|-----------------|--------------------------------------------------|----------|
| User            | `~/.local/share/PortProtonQT/custom_data/`       | Highest  |
| Built-in        | `portprotonqt/custom_data/`                      | Lower    |

---

## ⚙️ How It Works

### Data Priorities

Data is used in the following order:

1. **User Overrides**
2. **Built-in Overrides**
3. **Steam Metadata**
4. **`.desktop` file info**

### File Structure

Each `<exe_name>` folder can include:

- `metadata.txt` — contains name and description:
  ```txt
  name=My Game Title
  name_ru=My Game Title (in russian language)
  description=My Game Description
  description_ru=My Game Description (in russian language)
  ```
- `cover.<extension>` — image file (`.png`, `.jpg`, `.jpeg`, `.bmp`)

---

## 👤 For Users

### Creating User Overrides

1. **Create a folder for your game**:
   ```bash
   mkdir -p ~/.local/share/PortProtonQT/custom_data/mygame
   ```

2. **Add overrides**:
   - **Metadata file**:
     ```bash
     echo -e "name=My Game\ndescription=Exciting game" > ~/.local/share/PortProtonQT/custom_data/mygame/metadata.txt
     ```
   - **Cover image**:
     ```bash
     cp ~/Images/custom_cover.png ~/.local/share/PortProtonQT/custom_data/mygame/cover.png
     ```

3. **Restart PortProtonQT**.

## 🛠 For Developers

### Adding Built-In Overrides

1. **Create a folder in the project**:
   ```bash
   mkdir -p portprotonqt/custom_data/mygame
   ```

2. **Add files**:

- `metadata.txt`:
  ```txt
  name=Default Title
  description=Default Description
  ```

- Cover image (`cover.png`, for example):
  ```bash
  cp path/to/cover.png portprotonqt/custom_data/mygame/cover.png
  ```

3. **Commit changes to repository**:
   ```bash
   git add portprotonqt/custom_data/mygame
   git commit -m "Added built-in overrides for mygame"
   ```

---

> Done! Your games will now look exactly how you want 🎮✨
