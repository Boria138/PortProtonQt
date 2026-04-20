📘  Эта документация также доступна на [русском](README.ru.md)

---

## 📋 Contents
- [Overview](#-overview)
- [How It Works](#-how-it-works)
- [For Users](#-for-users)
- [For Developers](#-for-developers)

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
| Remote defaults | `PortProtonQt-Custom-Metadata` repository        | Lower    |

---

## ⚙️ How It Works

### Data Priorities

Data is used in the following order:

1. **User Overrides**
2. **Remote defaults**
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

### Adding Remote Defaults

Add metadata and covers in:
`https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt-Custom-Metadata`

---

> Done! Your games will now look exactly how you want 🎮✨
