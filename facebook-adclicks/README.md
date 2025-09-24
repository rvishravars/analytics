# INFO411 Online Data Joiner Presentation

This presentation uses [reveal‑md](https://github.com/webpro/reveal-md), a command‑line tool that converts Markdown files into reveal.js presentations.

## Prerequisites

- [Node.js](https://nodejs.org/) (includes npm)

## Installing Node.js

### Ubuntu/Debian

You can install Node.js via your system package manager:
```bash
sudo apt update
sudo apt install nodejs npm
```
Alternatively, consider using [nvm](https://github.com/nvm-sh/nvm):
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
# Restart your terminal or source your profile, then install Node:
nvm install node
```

### Fedora

Install Node.js using dnf:
```bash
sudo dnf install nodejs npm
```
Or use [nvm](https://github.com/nvm-sh/nvm) for more control:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
# Restart your terminal or source your profile, then install Node:
nvm install node
```

### macOS

You can install Node.js using Homebrew:
```bash
brew update
brew install node
```
Alternatively, install via [nvm](https://github.com/nvm-sh/nvm):
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
# Restart your terminal or source your profile, then install Node:
nvm install node
```

### Windows

Download the Node.js installer from the [official website](https://nodejs.org/) and follow the installation instructions.  
Alternatively, you can use [nvm-windows](https://github.com/coreybutler/nvm-windows) for managing Node.js versions.

## Installing reveal‑md

Install reveal‑md globally using npm:
```bash
npm install -g reveal-md
```

## Serving the Presentation Locally

To preview the presentation in your browser, run:
```bash
reveal-md Presentation.md --theme beige --css presentation.css
```
By default, the presentation will be available at [http://localhost:1948](http://localhost:1948).

## Exporting a Static Presentation

You can export your presentation as a static website using:
```bash
reveal-md Presentation.md --static presentation --theme beige --css presentation.css
```
This generates a static version of your presentation in the `presentation` directory. You can serve these files using any static server or deploy them (e.g., on GitHub Pages).

## Additional Tips

- Use `---` to separate horizontal slides and `----` to separate vertical slides in your Markdown file.
- Check the [reveal‑md documentation](https://github.com/webpro/reveal-md) for additional options and configurations.

---