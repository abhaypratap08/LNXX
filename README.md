# LNXX

LNXX is a Linux terminal trainer driven by hands-on practice, built for people who want to actually get comfortable in the shell.

Real commands, a fake filesystem, and just enough structure to keep you moving without turning it into a lecture.

## Install

The installer creates a private Python virtual environment at `~/.lnxx/.venv` and installs LNXX's Python dependencies there. It never installs Python packages into the system interpreter.

It also configures the launcher path for Bash, Zsh, and Fish.

```bash
curl -fsSL https://raw.githubusercontent.com/abhaypratap08/LNXX/main/install.sh | bash
```

After installation, open a new terminal and run:

```bash
lnxx
```
