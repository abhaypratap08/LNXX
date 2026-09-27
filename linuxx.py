#!/usr/bin/env python3
"""
LNXX — your safe terminal playground (TUI).
Run:     python3 linuxx.py            (TUI is the default; --tui also works)
Tests:   python3 linuxx.py --test
Classic CLI was removed. Engine (FakeShell, lessons, editors) + Textual TUI.
TUI needs the 'textual' package (auto-installed on launch if missing).
Python 3.8+.
"""

import json
import io
import os
import random
import re
import shlex
import sys
import subprocess
import textwrap
import time
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SAVE_FILE = os.path.expanduser("~/.capto_progress.json")

# ─────────────────────────── UI ───────────────────────────

class UI:
    USE_COLOR = (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and os.environ.get("NO_COLOR") is None
        and (
            os.name != "nt"
            or os.environ.get("WT_SESSION")
            or os.environ.get("ANSICON")
            or os.environ.get("TERM_PROGRAM")
        )
    )

    RESET  = "\033[0m"  if USE_COLOR else ""
    BOLD   = "\033[1m"  if USE_COLOR else ""
    DIM    = "\033[2m"  if USE_COLOR else ""
    ITALIC = "\033[3m"  if USE_COLOR else ""
    RED    = "\033[31m" if USE_COLOR else ""
    GREEN  = "\033[32m" if USE_COLOR else ""
    YELLOW = "\033[33m" if USE_COLOR else ""
    BLUE   = "\033[34m" if USE_COLOR else ""
    MAGENTA= "\033[35m" if USE_COLOR else ""
    CYAN   = "\033[36m" if USE_COLOR else ""
    WHITE  = "\033[97m" if USE_COLOR else ""

    @staticmethod
    def c(text: str, *codes: str) -> str:
        if not UI.USE_COLOR:
            return text
        return "".join(codes) + text + UI.RESET

    @staticmethod
    def clear() -> None:
        print("\n" * 40)

    @staticmethod
    def width(default: int = 100) -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return default

    @staticmethod
    def rule(char: str = "─") -> str:
        try:
            safe = char if len(char) == 1 else "─"
            return safe * min(UI.width(), 100)
        except Exception:
            return "-" * 80

    @staticmethod
    def box(title: str, body: str, color: str = "") -> str:
        color = color or UI.CYAN
        w = min(UI.width(), 100)
        inner = w - 4
        lines = []
        clean = f" {title} "
        if len(clean) > inner:
            clean = clean[:inner]
        pad = max(0, inner - len(clean))
        lines.append(UI.c("╔" + "═" * (len(clean) + pad) + "╗", color))
        lines.append(UI.c("║", color) + UI.c(clean, UI.BOLD, UI.WHITE) + " " * pad + UI.c("║", color))
        lines.append(UI.c("╠" + "═" * (len(clean) + pad) + "╣", color))
        for para in body.split("\n"):
            if para.strip() == "":
                lines.append(UI.c("║", color) + " " * (w - 2) + UI.c("║", color))
                continue
            wrapped = textwrap.wrap(para, width=inner) or [""]
            for wr in wrapped:
                lines.append(UI.c("║", color) + " " + wr.ljust(inner) + " " + UI.c("║", color))
        lines.append(UI.c("╚" + "═" * (len(clean) + pad) + "╝", color))
        return "\n".join(lines)

    @staticmethod
    def pause() -> None:
        input(UI.c("\n  Press Enter to continue…", UI.DIM))

    @staticmethod
    def banner() -> str:
        brand = (UI.c("  🌱 LNXX", UI.BOLD + UI.YELLOW) +
                 UI.c("  ·  your safe terminal playground — nothing real can break", UI.DIM))
        prompt  = (UI.c("  capto@linux-lab", UI.BOLD + UI.GREEN) +
                   UI.c(":", UI.WHITE) +
                   UI.c("~", UI.BOLD + UI.BLUE) +
                   UI.c("$ ", UI.WHITE) +
                   UI.c("come learn linux", UI.BOLD + UI.CYAN))
        return brand + "\n" + prompt

    @staticmethod
    def capto(text: str) -> str:
        return UI.c("  🦊 Capto82: ", UI.BOLD + UI.MAGENTA) + text

    @staticmethod
    def level_badge(level: int) -> str:
        badges = {1:"🐣",2:"🌱",3:"⚡",4:"🔥",5:"💎",6:"👑",7:"🦾",8:"🚀",9:"🌌",10:"🏆"}
        return badges.get(min(level, 10), "🏆")

    @staticmethod
    def xp_bar(xp: int, max_xp: int, width: int = 20) -> str:
        filled = int((xp / max(max_xp, 1)) * width)
        bar = "█" * filled + "░" * (width - filled)
        return UI.c(f"[{bar}]", UI.GREEN)


# ─────────────────────────── Data ───────────────────────────

@dataclass
class Mission:
    prompt: str
    accepted: List[str]
    hint: str
    explanation: str
    xp: int = 10


@dataclass
class Lesson:
    command: str
    title: str
    concept: str
    syntax: str
    examples: List[str]
    mistakes: List[str]
    pro_tip: str = ""
    missions: List[Mission] = field(default_factory=list)


LESSONS: List[Lesson] = [
    Lesson(
        command="pwd",
        title="Print current directory",
        concept=(
            "pwd stands for 'print working directory'. It tells you exactly where you are in the "
            "filesystem tree — your current location. Think of it as asking your GPS: where am I right now?"
        ),
        syntax="pwd",
        examples=["pwd"],
        mistakes=[
            "pwd takes no arguments — it just prints your location.",
            "pwd shows location; ls shows what is inside that location.",
        ],
        pro_tip="pwd is especially useful inside scripts to verify the working directory before doing file operations.",
        missions=[
            Mission(
                "Show your current working directory.",
                ["pwd"],
                "Just type pwd — no arguments needed.",
                "pwd prints the absolute path from / to your current directory.",
                xp=5,
            )
        ],
    ),
    Lesson(
        command="ls",
        title="List directory contents",
        concept=(
            "ls lists files and directories. Key flags: -l (long format with permissions/size/date), "
            "-a (include hidden dotfiles), -h (human-readable sizes), -t (sort by time). "
            "Flags can be combined: ls -lah shows everything in detail."
        ),
        syntax="ls [options] [path]",
        examples=["ls", "ls -l", "ls -a", "ls -lah", "ls /etc"],
        mistakes=[
            "Hidden files start with a dot. You need -a to see them.",
            "ls -la and ls -al are equivalent — flag order does not matter.",
            "ls /some/path lists that directory without changing your location.",
        ],
        pro_tip="alias ll='ls -lah' is one of the most common shell aliases. It is already in your .bashrc here.",
        missions=[
            Mission(
                "List everything in the current directory including hidden files.",
                ["ls -a", "ls -la", "ls -al", "ls -lah", "ls -ahl"],
                "Hidden files need the -a flag.",
                "-a stands for 'all'. It reveals dotfiles like .bashrc and .profile.",
                xp=10,
            ),
            Mission(
                "Show a long detailed listing of the current directory.",
                ["ls -l", "ls -la", "ls -al", "ls -lh", "ls -lah"],
                "Use the long-listing flag -l.",
                "-l shows permissions, owner, group, file size, modification date, and name.",
                xp=10,
            ),
        ],
    ),
    Lesson(
        command="cd",
        title="Change directory",
        concept=(
            "cd navigates the filesystem. Absolute paths start with / and work from anywhere. "
            "Relative paths start from your current position. Special shortcuts: ~ is your home, "
            ".. is parent directory, - takes you back to the previous directory."
        ),
        syntax="cd [path]",
        examples=["cd Documents", "cd ..", "cd /etc", "cd ~", "cd -"],
        mistakes=[
            "cd only works on directories, not files.",
            "cd .. moves up one level; cd ../.. moves up two levels.",
            "cd with no argument is the same as cd ~ — it takes you home.",
        ],
        pro_tip="cd - is a hidden gem. It bounces you back to whichever directory you were in before.",
        missions=[
            Mission(
                "Navigate into the Documents directory.",
                ["cd Documents", "cd ./Documents"],
                "Type cd followed by the directory name.",
                "cd Documents changes your current position to the Documents folder.",
                xp=10,
            ),
            Mission(
                "Move one directory level upward.",
                ["cd .."],
                "Two dots always mean the parent directory.",
                ".. is the parent of any directory. cd .. climbs one level up the tree.",
                xp=5,
            ),
        ],
    ),
    Lesson(
        command="mkdir",
        title="Create directories",
        concept=(
            "mkdir creates new directories. With -p it creates the full path including any missing parent "
            "directories in one go. You can create multiple directories at once by listing them: "
            "mkdir notes drafts archive"
        ),
        syntax="mkdir [-p] directory_name ...",
        examples=["mkdir notes", "mkdir -p projects/linux/week1", "mkdir notes drafts archive"],
        mistakes=[
            "Use touch for files and mkdir for directories — they are different things.",
            "mkdir projects/day1 fails if 'projects' doesn't exist yet. Add -p to auto-create parents.",
        ],
        pro_tip="mkdir -p is essential in scripts. It is safe to re-run — it won't error if the directory already exists.",
        missions=[
            Mission(
                "Create a directory named practice.",
                ["mkdir practice"],
                "Use mkdir followed by the new directory name.",
                "mkdir practice creates a new empty directory in your current location.",
                xp=10,
            ),
            Mission(
                "Create a nested path projects/linux in one command.",
                ["mkdir -p projects/linux"],
                "The -p flag creates all missing parent directories.",
                "mkdir -p creates the entire path at once, no matter how deep.",
                xp=15,
            ),
        ],
    ),
    Lesson(
        command="touch",
        title="Create files / update timestamps",
        concept=(
            "touch creates an empty file if it does not exist. If the file does exist, it simply "
            "updates the access and modification timestamps without changing the content. "
            "You can touch multiple files at once."
        ),
        syntax="touch file_name [file2 ...]",
        examples=["touch notes.txt", "touch app.py", "touch a.txt b.txt c.txt"],
        mistakes=[
            "touch does not open an editor — it just creates an empty file.",
            "touch a_folder creates a FILE named a_folder, not a directory.",
        ],
        pro_tip="touch is commonly used in scripts to create placeholder files or to force a build system to re-process a file.",
        missions=[
            Mission(
                "Create an empty file named todo.txt.",
                ["touch todo.txt"],
                "Type touch followed by the filename.",
                "touch todo.txt creates a zero-byte file. Confirm it exists with ls.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="cat",
        title="Display file contents",
        concept=(
            "cat (concatenate) prints file content to the terminal. It can also concatenate multiple files: "
            "cat a.txt b.txt prints both. For large files, use less (scrollable) or head/tail. "
            "cat -n adds line numbers."
        ),
        syntax="cat [options] file_name ...",
        examples=["cat readme.txt", "cat -n notes.txt", "cat a.txt b.txt"],
        mistakes=[
            "cat on a huge file floods the terminal. Use less for files longer than a screen.",
            "cat needs a readable file path — it will error on directories.",
        ],
        pro_tip="cat > newfile.txt lets you type content and save it to a file. Press Ctrl+D when done. (Try it in sandbox mode!)",
        missions=[
            Mission(
                "Display the contents of readme.txt.",
                ["cat readme.txt"],
                "Use cat with the filename.",
                "cat readme.txt dumps the entire file content to standard output.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="echo",
        title="Print text to terminal",
        concept=(
            "echo prints text or variable values to the terminal. It is essential in scripts for "
            "showing output and for writing text into files using redirection (> or >>). "
            "echo $HOME prints your home directory path."
        ),
        syntax="echo [text | $VARIABLE]",
        examples=["echo hello", 'echo "Linux is great"', "echo $HOME", "echo $USER"],
        mistakes=[
            "echo without quotes can misbehave with special characters like * or !.",
            "echo > file overwrites; echo >> file appends. The difference matters.",
        ],
        pro_tip="echo $? prints the exit code of the last command. 0 means success; non-zero means something failed.",
        missions=[
            Mission(
                "Print the word hello to the terminal.",
                ["echo hello", "echo 'hello'", 'echo "hello"'],
                "Use echo followed by what you want to print.",
                "echo writes its arguments to standard output followed by a newline.",
                xp=5,
            ),
            Mission(
                "Print your home directory using an environment variable.",
                ["echo $HOME"],
                "Environment variables start with $. Your home path is stored in $HOME.",
                "$HOME is a shell variable that holds the path to your home directory.",
                xp=10,
            ),
        ],
    ),
    Lesson(
        command="cp",
        title="Copy files and directories",
        concept=(
            "cp copies files or directories. The destination can be a new filename or an existing directory. "
            "Use -r for directories (recursive copy). Use -i to be prompted before overwriting. "
            "-p preserves timestamps and permissions."
        ),
        syntax="cp [options] source destination",
        examples=["cp notes.txt backup.txt", "cp -r project/ project_backup/", "cp -i file.txt /tmp/"],
        mistakes=[
            "Trying to copy a directory without -r will fail.",
            "cp overwrites silently by default. Use -i to get a confirmation prompt.",
        ],
        pro_tip="cp -r src/ dst/ (with trailing slash on source) copies the contents; cp -r src dst/ copies the directory itself inside dst.",
        missions=[
            Mission(
                "Copy readme.txt to readme_backup.txt.",
                ["cp readme.txt readme_backup.txt"],
                "cp source destination",
                "cp creates an independent copy. Editing one won't affect the other.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="mv",
        title="Move or rename files",
        concept=(
            "mv moves files or directories. When source and destination are in the same directory, "
            "it effectively renames the file. When moving to a different path, it relocates it. "
            "Unlike cp, mv does not create a copy — the original is gone."
        ),
        syntax="mv source destination",
        examples=["mv old.txt new.txt", "mv notes.txt Documents/", "mv *.log /tmp/logs/"],
        mistakes=[
            "mv overwrites the destination without warning if it already exists.",
            "mv is both move and rename — there is no separate rename command in Linux.",
        ],
        pro_tip="mv is instant when moving within the same filesystem (just updates a pointer). Cross-device moves actually copy then delete.",
        missions=[
            Mission(
                "Rename old.txt to new.txt.",
                ["mv old.txt new.txt"],
                "Use mv old-name new-name to rename.",
                "mv old.txt new.txt renames the file in place. ls confirms old.txt is gone.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="rm",
        title="Remove files and directories",
        concept=(
            "rm permanently deletes files. There is no Recycle Bin — deletions are final. "
            "rm -r deletes directories recursively. rm -i asks for confirmation per file. "
            "NEVER run rm -rf / on a real system — it destroys everything."
        ),
        syntax="rm [options] path",
        examples=["rm temp.txt", "rm -r old_folder/", "rm -i *.log"],
        mistakes=[
            "rm does not move to trash — it deletes immediately.",
            "Always double-check the path before rm. Muscle memory has ended careers.",
            "rm -r is needed for directories; rm alone fails on them.",
        ],
        pro_tip="Before rm -r on something important, use ls on it first to confirm exactly what you are about to delete.",
        missions=[
            Mission(
                "Delete temp.txt.",
                ["rm temp.txt"],
                "Use rm followed by the filename.",
                "rm temp.txt removes the file permanently from the fake filesystem.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="grep",
        title="Search text patterns",
        concept=(
            "grep searches for lines matching a pattern. Essential flags: -i (case-insensitive), "
            "-n (show line numbers), -r (recursive directory search), -v (invert — lines that DON'T match), "
            "-c (count matching lines). grep supports regular expressions."
        ),
        syntax="grep [options] pattern file",
        examples=["grep error log.txt", "grep -i linux notes.txt", "grep -n main app.py", "grep -r TODO ."],
        mistakes=[
            "Patterns with spaces need quotes: grep 'hello world' file.txt",
            "grep is case-sensitive by default. Add -i for case-insensitive.",
            "grep searches file content, not filenames. Use find for filenames.",
        ],
        pro_tip="grep -r 'pattern' . searches recursively through every file in the current directory tree — extremely useful for codebases.",
        missions=[
            Mission(
                "Find all lines containing 'linux' in notes.txt.",
                ["grep linux notes.txt", "grep 'linux' notes.txt", 'grep "linux" notes.txt'],
                "grep pattern filename",
                "grep prints every line where the pattern appears.",
                xp=10,
            ),
            Mission(
                "Search for 'error' in log.txt ignoring case.",
                ["grep -i error log.txt", "grep -i 'error' log.txt"],
                "Case-insensitive search uses the -i flag.",
                "-i makes grep match ERROR, Error, error, eRrOr — all the same.",
                xp=15,
            ),
        ],
    ),
    Lesson(
        command="find",
        title="Search for files and directories",
        concept=(
            "find searches the filesystem tree for files/directories matching criteria. "
            "Key options: -name (glob pattern), -type f (files only), -type d (dirs only), "
            "-mtime (modified N days ago), -size. find is recursive by default."
        ),
        syntax="find [path] [expression]",
        examples=[
            "find . -name '*.txt'",
            "find /home -type d",
            "find . -name 'notes.txt'",
        ],
        mistakes=[
            "find . -name '*.txt' needs quotes around *.txt or the shell expands it first.",
            "find searches recursively. Starting from / on a real system is very slow.",
        ],
        pro_tip="Combine with -exec: find . -name '*.log' -exec rm {} \\; deletes all .log files found.",
        missions=[
            Mission(
                "Find all .txt files in the current directory tree.",
                ["find . -name '*.txt'", 'find . -name "*.txt"'],
                "Use find . -name '*.txt' — the dot means start here.",
                "find . -name '*.txt' recursively lists every .txt file below the current directory.",
                xp=15,
            )
        ],
    ),
    Lesson(
        command="wc",
        title="Count words, lines, characters",
        concept=(
            "wc (word count) counts lines (-l), words (-w), and characters (-c) in files. "
            "Running wc alone shows all three. It is great for quick stats on log files, "
            "codebases, or any text output piped into it."
        ),
        syntax="wc [options] file",
        examples=["wc notes.txt", "wc -l log.txt", "wc -w readme.txt"],
        mistakes=[
            "wc -l counts newlines, so the last line might not be counted if it has no trailing newline.",
        ],
        pro_tip="Pipe output into wc: ls | wc -l counts how many files are in a directory.",
        missions=[
            Mission(
                "Count the number of lines in log.txt.",
                ["wc -l log.txt"],
                "Use the -l flag for line count.",
                "wc -l prints the number of newline characters, which equals the number of lines.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="head/tail",
        title="Read beginning or end of files",
        concept=(
            "head shows the first N lines of a file (default 10). "
            "tail shows the last N lines. tail -f is the superpower: it follows the file live "
            "as new lines are written — essential for monitoring logs in real-time."
        ),
        syntax="head [-n N] file | tail [-n N] [-f] file",
        examples=["head notes.txt", "head -n 3 notes.txt", "tail log.txt", "tail -n 20 log.txt"],
        mistakes=[
            "Default is 10 lines. Use -n to specify a different number.",
            "tail -f keeps running. Press Ctrl+C to stop it on a real system.",
        ],
        pro_tip="tail -f /var/log/syslog on a real Linux system shows live system events as they happen.",
        missions=[
            Mission(
                "Show only the last lines of log.txt.",
                ["tail log.txt", "tail -n 10 log.txt"],
                "tail reads from the end of a file.",
                "tail prints the final lines. Useful for checking the latest log entries.",
                xp=10,
            ),
            Mission(
                "Show only the first 3 lines of notes.txt.",
                ["head -n 3 notes.txt"],
                "Use head with -n to specify the number of lines.",
                "-n 3 limits output to exactly 3 lines from the top.",
                xp=10,
            ),
        ],
    ),
    Lesson(
        command="chmod",
        title="Change file permissions",
        concept=(
            "chmod changes who can read, write, or execute a file. "
            "Symbolic mode: +x adds execute, -w removes write, u+x adds execute for owner. "
            "Numeric mode: each digit represents owner/group/others using 4=read, 2=write, 1=execute. "
            "755 = rwxr-xr-x. 644 = rw-r--r--."
        ),
        syntax="chmod mode file",
        examples=["chmod +x script.sh", "chmod 755 script.sh", "chmod 644 notes.txt", "chmod u+x,g-w file"],
        mistakes=[
            "Scripts need +x to be executable — writing the code is not enough.",
            "chmod 777 grants everyone full access. Usually a security mistake.",
        ],
        pro_tip="ls -l shows permissions as a string like -rwxr-xr-x. Read it as: type | owner | group | others.",
        missions=[
            Mission(
                "Make script.sh executable.",
                ["chmod +x script.sh", "chmod 755 script.sh"],
                "+x adds execute permission.",
                "+x makes a file runnable. Without it, the shell refuses to execute it.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="ps/kill",
        title="Inspect and manage processes",
        concept=(
            "ps shows running processes. Common: ps aux (all processes, all users, full details). "
            "kill sends a signal to a process by PID. kill -15 (SIGTERM) is polite; "
            "kill -9 (SIGKILL) is forceful and immediate. Use kill -9 only as a last resort."
        ),
        syntax="ps [aux] | kill [-signal] PID",
        examples=["ps", "ps aux", "kill 1234", "kill -9 1234"],
        mistakes=[
            "kill takes a PID, not a program name. Use pgrep or pidof to find a PID by name.",
            "kill -9 bypasses cleanup. The process cannot save state or close files gracefully.",
        ],
        pro_tip="ps aux | grep python lists only Python processes. Combine ps with grep to find exactly what you need.",
        missions=[
            Mission(
                "List all running processes.",
                ["ps", "ps aux"],
                "ps shows the process table.",
                "ps displays each running process with its PID, state, and command.",
                xp=10,
            )
        ],
    ),
    Lesson(
        command="pipe (|)",
        title="Chain commands with pipes",
        concept=(
            "The pipe | connects the output of one command to the input of the next. "
            "This is the Unix philosophy in action: small tools, chained together, become powerful. "
            "ls | wc -l counts files. cat file.txt | grep error filters lines. Chains can be arbitrarily long."
        ),
        syntax="command1 | command2 | command3",
        examples=[
            "ls | wc -l",
            "cat log.txt | grep ERROR",
            "ps aux | grep python",
            "cat notes.txt | grep linux | wc -l",
        ],
        mistakes=[
            "Each command in a pipe runs as a separate process — they run concurrently.",
            "If the first command produces no output, later commands get nothing.",
        ],
        pro_tip="You can pipe as many commands as you want. The output flows left to right like water through pipes.",
        missions=[
            Mission(
                "Count how many files are in the current directory using a pipe.",
                ["ls | wc -l"],
                "Pipe ls output into wc -l to count entries.",
                "ls lists files, | passes that list to wc -l which counts the lines.",
                xp=20,
            ),
            Mission(
                "Find lines with 'error' in log.txt using cat and grep piped together.",
                ["cat log.txt | grep error", "cat log.txt | grep 'error'"],
                "Pipe cat output into grep.",
                "cat outputs the file; grep filters it. Same result as grep error log.txt but teaches piping.",
                xp=15,
            ),
        ],
    ),
]


AFFIRMATIONS = [
    "Capto is genuinely impressed rn.",
    "Demmmn. Terminal aura just went up.",
    "Are you trying to rizz Linus Torvalds or something?",
    "Clean execution. No fluff, just progress.",
    "Bro is slowly becoming the shell operator.",
    "That landed perfectly. Keep shipping.",
    "Linux fear: -1. Shell confidence: +1.",
    "One command closer to running a server at 2am like it's nothing.",
    "Capto does not give out easy compliments. This one is earned.",
    "You're building muscle memory. That's the whole game.",
    "Real one. No IDE. Just the terminal.",
    "That's the one. Clean and correct.",
    "Capto is proud of his students. Especially the ones who type Linux commands like this.",
    "Capto saw that command and quietly nodded.",
    "Linux did not scare you today. Good.",
    "abhaypratap would approve this terminal behavior.",
    "what are you trying to rizz travis travolds ?",
    "This is the kind of Linux confidence Capto was built for.",
    "abhaypratap put the mission there, you handled it.",
    "Capto says: no panic, just pathnames.",
    "That command had clean Linux energy.",
    "You are not memorizing anymore, you are operating.",
    "Capto is writing this one down as progress.",
    "Linux shell looking less mysterious by the minute.",
    "abhaypratap did not build LNXX for weak attempts. This was solid.",
    "Capto rates that command: dangerously competent.",
    "You just made the terminal blink first.",
    "That was not luck. That was Linux muscle memory loading.",
    "Capto is proud, but he will act normal about it.",
    "abhaypratap's student arc is getting serious.",
    "Tiny command, big operator behavior.",
    "Linux unlocked one more door for you.",
    "Capto saw no hesitation there.",
    "You are slowly becoming the person people ask for terminal help.",
    "That answer had root-user confidence without root-user recklessness.",
    "abhaypratap would call that clean execution.",
    "Capto is proud of his students, and this quiz answer proves why.",
    "Linux checkpoint cleared. Capto is watching the glow-up.",
    "abhaypratap asked for learning, you brought command-line discipline.",
    "Capto says that answer was not a guess, that was Linux sense.",
    "Linux quiz survived. Student confidence increased.",
    "abhaypratap's LNXX student just passed another checkpoint.",
    "Capto is proud of this answer. Do not let it go to your head.",
    "Linux concepts are starting to stick. Capto noticed.",
    "abhaypratap would save this one under clean quiz wins.",
    "Capto checkpoint cleared with actual brainpower.",
    "That was Linux understanding, not copy-paste energy.",
    "Capto approves. The terminal classroom remains undefeated.",
    "abhaypratap did not sneak that quiz in for nothing.",
    "Linux knowledge loading. Capto likes the progress bar.",
    "Capto is proud of his students when the answer hits like that.",
]

TIPS_OF_THE_DAY = [
    "Ctrl+R in bash searches your command history interactively.",
    "!! repeats your last command. sudo !! re-runs it with sudo.",
    "Ctrl+A jumps to the start of a line; Ctrl+E jumps to the end.",
    "Tab completion is your best friend — use it constantly.",
    "history | grep 'keyword' finds commands you ran before.",
    "man command shows the full manual page for any command.",
    "Use && to chain commands that only run if the previous succeeded: mkdir dir && cd dir",
    "Ctrl+C kills a running command. Ctrl+Z suspends it (then fg resumes it).",
    "Aliases in ~/.bashrc save you from typing long commands repeatedly.",
    "> overwrites a file; >> appends to it. Never confuse the two on real systems.",
]

QUIZ_QUESTIONS = {
    "pwd":      {"q": "What does pwd stand for and what does it display?",               "keys": ["working", "directory", "current", "path"]},
    "ls":       {"q": "Which ls option shows hidden dotfiles?",                          "keys": ["-a", "all", "hidden", "dot"]},
    "cd":       {"q": "What does cd .. do?",                                             "keys": ["parent", "up", "previous", "back", "level"]},
    "mkdir":    {"q": "Which flag lets mkdir create nested parent directories at once?", "keys": ["-p", "parents", "parent"]},
    "touch":    {"q": "What happens when you touch a file that already exists?",         "keys": ["timestamp", "time", "update", "modify", "nothing", "exists"]},
    "cat":      {"q": "What does cat stand for, and what is it mainly used for?",        "keys": ["concatenate", "display", "print", "show", "contents"]},
    "echo":     {"q": "What does echo $? print and why is it useful?",                   "keys": ["exit", "code", "status", "last", "error", "success"]},
    "cp":       {"q": "What flag does cp need to copy a directory?",                     "keys": ["-r", "recursive", "directory"]},
    "mv":       {"q": "What is the difference between mv and cp?",                       "keys": ["copy", "move", "original", "delete", "rename", "no copy"]},
    "rm":       {"q": "Why is rm considered dangerous compared to deleting in a GUI?",   "keys": ["trash", "permanent", "no recycle", "gone", "recover", "undo"]},
    "grep":     {"q": "What does the -i flag do in grep?",                               "keys": ["case", "insensitive", "ignore case", "uppercase", "lowercase"]},
    "find":     {"q": "How is find different from grep?",                                "keys": ["filename", "file name", "path", "name", "content"]},
    "wc":       {"q": "What does wc -l count?",                                          "keys": ["line", "lines", "newline"]},
    "head/tail":{"q": "What does tail -f do that makes it uniquely useful?",             "keys": ["follow", "live", "real time", "realtime", "watch", "monitor", "stream"]},
    "chmod":    {"q": "In numeric chmod, what does the number 7 represent for a digit?","keys": ["read write execute", "rwx", "all", "full", "4+2+1", "seven"]},
    "ps/kill":  {"q": "What is the difference between kill -15 and kill -9?",           "keys": ["graceful", "force", "sigterm", "sigkill", "cleanup", "immediate"]},
    "pipe (|)": {"q": "Describe in your own words what the pipe | operator does.",      "keys": ["output", "input", "connect", "chain", "pass", "next"]},
}

XP_THRESHOLDS = [0, 50, 120, 220, 360, 550, 800, 1120, 1520, 2020]  # XP needed to reach level N+1


# ─────────────────────────── Filesystem ───────────────────────────

@dataclass
class Node:
    type: str
    content: str = ""
    children: Dict[str, "Node"] = field(default_factory=dict)
    executable: bool = False


class FakeShell:
    def __init__(self):
        self.root = Node("dir")
        self.cwd: List[str] = ["home", "student"]
        self.score: int = 0
        self.xp: int = 0
        self.prev_cwd: Optional[List[str]] = None
        self.completed: set = set()
        self.commands_run: int = 0
        self.command_log: List[str] = []
        self.accomplished_commands: List[str] = []
        self.streak: int = 0
        self.reset_fs()

    def reset_fs(self) -> None:
        self.root = Node("dir")
        for path in [
            ["home"], ["home","student"], ["home","student","Documents"],
            ["home","student","Downloads"], ["home","student","projects"],
            ["home","student","projects","linux"],
        ]:
            self._mkdir_abs(path)
        files = {
            ("home","student","readme.txt"):    "Welcome to Linux Command Trainer.\nPractice safely inside this fake shell.\nCapto has your back.\n",
            ("home","student","notes.txt"):      "linux commands are composable\ngrep searches text\npractice beats passive reading\npipes are powerful\n",
            ("home","student","old.txt"):        "rename me\n",
            ("home","student","temp.txt"):       "temporary file\n",
            ("home","student","log.txt"):        "INFO  boot ok\nWARN  low memory\nERROR service failed\nINFO  retry successful\nERROR disk usage high\nINFO  backup complete\n",
            ("home","student","script.sh"):      "#!/bin/bash\necho hello from script\n",
            ("home","student",".bashrc"):        "alias ll='ls -lah'\nexport EDITOR=nano\n",
            ("home","student",".profile"):       "# user profile\nexport PATH=$PATH:$HOME/.local/bin\n",
            ("home","student","Documents","report.txt"): "Q3 results look promising.\nRevenue up 12 percent.\n",
        }
        for parts, content in files.items():
            self._write_abs(list(parts), content)
        self.cwd = ["home", "student"]

    def pwd(self) -> str:
        return "/" + "/".join(self.cwd)

    def _resolve(self, path: str) -> List[str]:
        if path in ("", "."):
            parts = self.cwd[:]
        elif path == "~":
            parts = ["home", "student"]
        elif path.startswith("~/"):
            parts = ["home", "student"] + [p for p in path[2:].split("/") if p]
        elif path.startswith("/"):
            parts = [p for p in path.split("/") if p]
        else:
            parts = self.cwd[:] + [p for p in path.split("/") if p]
        stack: List[str] = []
        for p in parts:
            if p == ".":
                continue
            if p == "..":
                if stack:
                    stack.pop()
            else:
                stack.append(p)
        return stack

    def _get_abs(self, parts: List[str]) -> Optional[Node]:
        node = self.root
        for p in parts:
            if node.type != "dir" or p not in node.children:
                return None
            node = node.children[p]
        return node

    def _parent_and_name(self, path: str) -> Tuple[Optional[Node], str]:
        parts = self._resolve(path)
        if not parts:
            return None, ""
        parent = self._get_abs(parts[:-1]) if len(parts) > 1 else self.root
        return parent, parts[-1]

    def _mkdir_abs(self, parts: List[str]) -> None:
        node = self.root
        for p in parts:
            node.children.setdefault(p, Node("dir"))
            node = node.children[p]

    def _write_abs(self, parts: List[str], content: str) -> None:
        parent = self._get_abs(parts[:-1]) if len(parts) > 1 else self.root
        if parent and parent.type == "dir":
            parent.children[parts[-1]] = Node("file", content=content)

    def _clone(self, node: Node) -> Node:
        return Node(node.type, node.content, {k: self._clone(v) for k, v in node.children.items()}, node.executable)

    def _shell_tokens(self, raw: str, redirects: bool = False) -> Tuple[Optional[List[str]], Optional[str]]:
        try:
            if redirects:
                lexer = shlex.shlex(raw, posix=True, punctuation_chars=">")
                lexer.whitespace_split = True
                return list(lexer), None
            return shlex.split(raw), None
        except ValueError as e:
            return None, f"syntax error: {e}"

    def _is_descendant(self, child: List[str], parent: List[str]) -> bool:
        return len(child) > len(parent) and child[:len(parent)] == parent

    def run(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ""
        if raw == "!!":
            if not self.command_log:
                return "bash: !!: event not found"
            raw = self.command_log[-1]
        self.commands_run += 1
        self.command_log.append(raw)

        # Handle pipes: split on | then chain
        if "|" in raw:
            return self._run_pipe(raw)

        redirect_args, redirect_error = self._shell_tokens(raw, redirects=True)
        if redirect_error:
            return redirect_error

        # Redirect: echo text > file  /  cat > file
        if redirect_args and any(token in (">", ">>") for token in redirect_args):
            return self._handle_redirect(redirect_args)

        args, parse_error = self._shell_tokens(raw)
        if parse_error:
            return parse_error
        if not args:
            return ""

        cmd = args[0]
        rest = args[1:]

        handlers = {
            "pwd":   self.cmd_pwd,
            "ls":    self.cmd_ls,
            "cd":    self.cmd_cd,
            "mkdir": self.cmd_mkdir,
            "touch": self.cmd_touch,
            "cat":   self.cmd_cat,
            "echo":  self.cmd_echo,
            "cp":    self.cmd_cp,
            "mv":    self.cmd_mv,
            "rm":    self.cmd_rm,
            "grep":  self.cmd_grep,
            "find":  self.cmd_find,
            "wc":    self.cmd_wc,
            "head":  self.cmd_head,
            "tail":  self.cmd_tail,
            "chmod": self.cmd_chmod,
            "ps":    self.cmd_ps,
            "kill":  self.cmd_kill,
            "history": self.cmd_history,
            "clear": lambda _: "__CLEAR__",
            "reset": lambda _: self._do_reset(),
            "help":  lambda _: self._help(),
            # editors — signal the app layer to open interactive editor
            "nano":  lambda a: f"__EDITOR__:nano:{a[0] if a else ''}",
            "vim":   lambda a: f"__EDITOR__:vim:{a[0] if a else ''}",
            "nvim":  lambda a: f"__EDITOR__:vim:{a[0] if a else ''}",
            "vi":    lambda a: f"__EDITOR__:vim:{a[0] if a else ''}",
        }

        if cmd not in handlers:
            return f"{cmd}: command not found. Type help for available commands."
        return handlers[cmd](rest)

    def _run_pipe(self, raw: str) -> str:
        """Execute a pipeline. Each stage's stdout feeds the next stage's stdin."""
        segments = [s.strip() for s in raw.split("|")]
        current_input = None
        for seg in segments:
            if not seg:
                return "syntax error near |"
            try:
                args = shlex.split(seg)
            except ValueError as e:
                return f"syntax error: {e}"
            cmd = args[0]
            rest = args[1:]
            # Commands that can accept piped stdin
            if cmd == "wc":
                result = self._wc_stdin(rest, current_input or "")
            elif cmd == "grep":
                result = self._grep_stdin(rest, current_input or "")
            elif cmd == "head":
                result = self._head_tail_stdin(rest, current_input or "", head=True)
            elif cmd == "tail":
                result = self._head_tail_stdin(rest, current_input or "", head=False)
            elif cmd == "cat":
                if rest:
                    result = self.cmd_cat(rest)
                else:
                    result = current_input or ""
            elif cmd == "ls":
                result = self.cmd_ls(rest)
            elif cmd == "ps":
                result = self.cmd_ps(rest)
            elif cmd == "history":
                result = self.cmd_history(rest)
            elif cmd == "echo":
                result = self.cmd_echo(rest)
            elif cmd == "sort":
                lines = (current_input or "").splitlines()
                result = "\n".join(sorted(lines))
            elif cmd == "uniq":
                lines = (current_input or "").splitlines()
                seen = []
                for line in lines:
                    if not seen or seen[-1] != line:
                        seen.append(line)
                result = "\n".join(seen)
            else:
                result = f"{cmd}: not available in pipeline"
            current_input = result
        return current_input or ""

    def _help(self) -> str:
        return (
            "Available commands: pwd, ls, cd, mkdir, touch, cat, echo, cp, mv, rm,\n"
            "                    grep, find, wc, head, tail, chmod, ps, kill, history\n"
            "Editors:            nano <file>   vim <file>   vi <file>   nvim <file>\n"
            "Redirect:           echo text > file   echo text >> file   cat > file\n"
            "Special:            !! (repeat last command), clear, reset (restore filesystem), help\n"
            "Piping:             command1 | command2  (chain commands)"
        )

    def _handle_redirect(self, args: List[str]) -> str:
        """Handle  cmd > file  and  cmd >> file  redirects."""
        redirect_positions = [i for i, token in enumerate(args) if token in (">", ">>")]
        if len(redirect_positions) != 1:
            return "redirect: syntax error"
        pos = redirect_positions[0]
        if pos == 0 or pos + 1 >= len(args) or pos + 2 != len(args):
            return "redirect: syntax error"

        append = args[pos] == ">>"
        left_args = args[:pos]
        fpath = args[pos + 1]
        if not fpath:
            return "redirect: missing filename"

        if left_args == ["cat"]:
            out_text = ""
        else:
            out_text = self._run_args(left_args)

        if out_text.startswith("__"):
            return "redirect: cannot redirect special commands"
        parent, name = self._parent_and_name(fpath)
        if not parent or parent.type != "dir":
            return f"bash: {fpath}: No such file or directory"
        existing_node = parent.children.get(name)
        if existing_node and existing_node.type == "dir":
            return f"bash: {fpath}: Is a directory"
        if append:
            existing = existing_node.content if existing_node else ""
            parent.children[name] = Node("file", content=existing + out_text + "\n")
        else:
            parent.children[name] = Node("file", content=out_text + "\n")
        return ""

    def _run_args(self, args: List[str]) -> str:
        cmd = args[0]
        rest = args[1:]
        handlers = {
            "pwd":   self.cmd_pwd,
            "ls":    self.cmd_ls,
            "cat":   self.cmd_cat,
            "echo":  self.cmd_echo,
            "grep":  self.cmd_grep,
            "find":  self.cmd_find,
            "wc":    self.cmd_wc,
            "head":  self.cmd_head,
            "tail":  self.cmd_tail,
            "ps":    self.cmd_ps,
            "history": self.cmd_history,
            "help":  lambda _: self._help(),
        }
        if cmd not in handlers:
            return f"{cmd}: command not found. Type help for available commands."
        return handlers[cmd](rest)

    def _do_reset(self) -> str:
        self.reset_fs()
        return "Filesystem restored to initial state."

    def cmd_pwd(self, args: List[str]) -> str:
        return self.pwd()

    def cmd_ls(self, args: List[str]) -> str:
        show_all = any("a" in a.lstrip("-") for a in args if a.startswith("-"))
        long_fmt = any("l" in a.lstrip("-") for a in args if a.startswith("-"))
        paths = [a for a in args if not a.startswith("-")]
        target = paths[0] if paths else "."
        node = self._get_abs(self._resolve(target))
        if node is None:
            return f"ls: cannot access '{target}': No such file or directory"
        if node.type == "file":
            return target
        names = sorted(node.children.keys())
        if not show_all:
            names = [n for n in names if not n.startswith(".")]
        if long_fmt:
            rows = []
            for n in names:
                child = node.children[n]
                if child.type == "dir":
                    perm = "drwxr-xr-x"
                elif child.executable:
                    perm = "-rwxr-xr-x"
                else:
                    perm = "-rw-r--r--"
                size = len(child.content) if child.type == "file" else 4096
                rows.append(f"{perm}  student student  {size:>5}  {n}")
            return "\n".join(rows)
        return "\n".join(names)

    def cmd_cd(self, args: List[str]) -> str:
        path = args[0] if args else "~"
        if path == "-":
            if self.prev_cwd is None:
                return "cd: OLDPWD not set"
            self.prev_cwd, self.cwd = self.cwd, self.prev_cwd
            return self.pwd()
        parts = self._resolve(path)
        node = self._get_abs(parts)
        if node is None:
            return f"cd: no such file or directory: {path}"
        if node.type != "dir":
            return f"cd: not a directory: {path}"
        self.prev_cwd = self.cwd[:]
        self.cwd = parts
        return ""

    def cmd_mkdir(self, args: List[str]) -> str:
        if not args:
            return "mkdir: missing operand"
        parents = "-p" in args
        targets = [a for a in args if not a.startswith("-")]
        out = []
        for target in targets:
            parts = self._resolve(target)
            if parents:
                self._mkdir_abs(parts)
            else:
                parent = self._get_abs(parts[:-1]) if len(parts) > 1 else self.root
                if not parent or parent.type != "dir":
                    out.append(f"mkdir: cannot create directory '{target}': No such file or directory")
                elif parts[-1] in parent.children:
                    out.append(f"mkdir: cannot create directory '{target}': File exists")
                else:
                    parent.children[parts[-1]] = Node("dir")
        return "\n".join(out)

    def cmd_touch(self, args: List[str]) -> str:
        if not args:
            return "touch: missing file operand"
        out = []
        for path in args:
            parent, name = self._parent_and_name(path)
            if not parent or parent.type != "dir":
                out.append(f"touch: cannot touch '{path}': No such file or directory")
            else:
                parent.children.setdefault(name, Node("file"))
        return "\n".join(out)

    def cmd_cat(self, args: List[str]) -> str:
        if not args:
            return "cat: missing file operand"
        show_lines = "-n" in args
        paths = [a for a in args if not a.startswith("-")]
        out = []
        for path in paths:
            node = self._get_abs(self._resolve(path))
            if node is None:
                out.append(f"cat: {path}: No such file")
            elif node.type != "file":
                out.append(f"cat: {path}: Is a directory")
            else:
                content = node.content.rstrip("\n")
                if show_lines:
                    numbered = "\n".join(f"{i+1:>4}  {line}" for i, line in enumerate(content.splitlines()))
                    out.append(numbered)
                else:
                    out.append(content)
        return "\n".join(out)

    def cmd_echo(self, args: List[str]) -> str:
        text = " ".join(args)
        env = {"$HOME": "/home/student", "$USER": "student", "$SHELL": "/bin/bash",
               "$PWD": self.pwd(), "$?": "0", "$HOSTNAME": "capto-lab"}
        for var, val in env.items():
            text = text.replace(var, val)
        return text

    def cmd_cp(self, args: List[str]) -> str:
        recursive = any(a in ("-r", "-R", "-rp", "-pr") for a in args)
        clean = [a for a in args if not a.startswith("-")]
        if len(clean) != 2:
            return "cp: expected source and destination"
        src, dst = clean
        src_node = self._get_abs(self._resolve(src))
        if src_node is None:
            return f"cp: cannot stat '{src}': No such file or directory"
        if src_node.type == "dir" and not recursive:
            return f"cp: -r not specified; omitting directory '{src}'"
        dst_node = self._get_abs(self._resolve(dst))
        if dst_node and dst_node.type == "dir":
            parent = dst_node
            name = self._resolve(src)[-1]
        else:
            parent, name = self._parent_and_name(dst)
            if not parent or parent.type != "dir":
                return f"cp: cannot create '{dst}': No such directory"
        parent.children[name] = self._clone(src_node)
        return ""

    def cmd_mv(self, args: List[str]) -> str:
        clean = [a for a in args if not a.startswith("-")]
        if len(clean) != 2:
            return "mv: expected source and destination"
        src, dst = clean
        src_parent, src_name = self._parent_and_name(src)
        if not src_parent or src_name not in src_parent.children:
            return f"mv: cannot stat '{src}': No such file or directory"
        src_parts = self._resolve(src)
        dst_parts = self._resolve(dst)
        if dst_parts == src_parts:
            return f"mv: '{src}' and '{dst}' are the same file"
        if self._is_descendant(dst_parts, src_parts):
            return f"mv: cannot move '{src}' to a subdirectory of itself, '{dst}'"
        dst_node = self._get_abs(dst_parts)
        if dst_node and dst_node.type == "dir":
            # move INTO that directory
            dst_parent = dst_node
            dst_name = src_name
        else:
            dst_parent, dst_name = self._parent_and_name(dst)
            if not dst_parent or dst_parent.type != "dir":
                return f"mv: cannot move to '{dst}': No such directory"
        dst_parent.children[dst_name] = src_parent.children.pop(src_name)
        return ""

    def cmd_rm(self, args: List[str]) -> str:
        if not args:
            return "rm: missing operand"
        recursive = any(a.startswith("-") and ("r" in a or "R" in a) for a in args)
        force = any(a.startswith("-") and "f" in a for a in args)
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return "" if force else "rm: missing operand"
        out = []
        for path in targets:
            parent, name = self._parent_and_name(path)
            if not parent or name not in parent.children:
                if not force:
                    out.append(f"rm: cannot remove '{path}': No such file or directory")
                continue
            node = parent.children[name]
            if node.type == "dir" and not recursive:
                out.append(f"rm: cannot remove '{path}': Is a directory")
                continue
            del parent.children[name]
        return "\n".join(out)

    def cmd_grep(self, args: List[str]) -> str:
        if not args:
            return "grep: missing pattern"
        ignore_case = show_line = invert = False
        clean = []
        for a in args:
            if a.startswith("-"):
                ignore_case = ignore_case or "i" in a
                show_line   = show_line   or "n" in a
                invert      = invert      or "v" in a
            else:
                clean.append(a)
        if len(clean) < 2:
            return "grep: expected pattern and file"
        pattern, path = clean[0], clean[1]
        node = self._get_abs(self._resolve(path))
        if node is None or node.type != "file":
            return f"grep: {path}: No such file"
        flags = re.IGNORECASE if ignore_case else 0
        out = []
        for i, line in enumerate(node.content.splitlines(), 1):
            match = bool(re.search(re.escape(pattern), line, flags))
            if match != invert:
                out.append(f"{i}:{line}" if show_line else line)
        return "\n".join(out)

    def _grep_stdin(self, args: List[str], stdin: str) -> str:
        ignore_case = show_line = invert = False
        clean = []
        for a in args:
            if a.startswith("-"):
                ignore_case = ignore_case or "i" in a
                show_line   = show_line   or "n" in a
                invert      = invert      or "v" in a
            else:
                clean.append(a)
        if not clean:
            return "grep: missing pattern"
        pattern = clean[0]
        flags = re.IGNORECASE if ignore_case else 0
        out = []
        for i, line in enumerate(stdin.splitlines(), 1):
            match = bool(re.search(re.escape(pattern), line, flags))
            if match != invert:
                out.append(f"{i}:{line}" if show_line else line)
        return "\n".join(out)

    def cmd_find(self, args: List[str]) -> str:
        start = "."
        name_pattern = None
        find_type = None
        i = 0
        while i < len(args):
            if args[i] == "-name" and i + 1 < len(args):
                name_pattern = args[i+1].strip("'\"")
                i += 2
            elif args[i] == "-type" and i + 1 < len(args):
                find_type = args[i+1]
                i += 2
            elif not args[i].startswith("-"):
                start = args[i]
                i += 1
            else:
                i += 1
        start_parts = self._resolve(start)
        results = []
        self._find_recurse(self._get_abs(start_parts), start_parts, name_pattern, find_type, results)
        return "\n".join(results) if results else ""

    def _find_recurse(self, node: Optional[Node], parts: List[str], name_pat: Optional[str], ftype: Optional[str], results: List[str]) -> None:
        if node is None:
            return
        path_str = "/" + "/".join(parts) if parts else "/"
        if path_str == "/":
            path_str = "."
        else:
            rel_parts = parts[len(self.cwd):]
            path_str = ("." + ("/" + "/".join(rel_parts) if rel_parts else ""))
        name = parts[-1] if parts else ""
        type_ok = (ftype is None) or (ftype == "f" and node.type == "file") or (ftype == "d" and node.type == "dir")
        name_ok = (name_pat is None) or self._glob_match(name, name_pat)
        if parts and parts != self._resolve(".") and type_ok and name_ok:
            rel = parts[len(self._resolve(".")):] if len(parts) >= len(self._resolve(".")) else parts
            rel_path = "./".rstrip("/") + ("/" + "/".join(rel) if rel else "")
            results.append(rel_path)
        if node.type == "dir":
            for child_name, child_node in sorted(node.children.items()):
                self._find_recurse(child_node, parts + [child_name], name_pat, ftype, results)

    def _glob_match(self, name: str, pattern: str) -> bool:
        regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
        return bool(re.fullmatch(regex, name))

    def cmd_wc(self, args: List[str]) -> str:
        count_l = "-l" in args
        count_w = "-w" in args
        count_c = "-c" in args
        all_counts = not (count_l or count_w or count_c)
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            return "wc: missing file operand"
        out = []
        for path in paths:
            node = self._get_abs(self._resolve(path))
            if node is None or node.type != "file":
                out.append(f"wc: {path}: No such file")
                continue
            content = node.content
            lines = len(content.splitlines())
            words = len(content.split())
            chars = len(content)
            if all_counts:
                out.append(f"  {lines}  {words}  {chars}  {path}")
            elif count_l:
                out.append(f"  {lines}  {path}")
            elif count_w:
                out.append(f"  {words}  {path}")
            elif count_c:
                out.append(f"  {chars}  {path}")
        return "\n".join(out)

    def _wc_stdin(self, args: List[str], stdin: str) -> str:
        count_l = "-l" in args
        count_w = "-w" in args
        count_c = "-c" in args
        all_counts = not (count_l or count_w or count_c)
        lines = len(stdin.splitlines())
        words = len(stdin.split())
        chars = len(stdin)
        if all_counts:
            return f"  {lines}  {words}  {chars}"
        if count_l:
            return str(lines)
        if count_w:
            return str(words)
        return str(chars)

    def cmd_head(self, args: List[str]) -> str:
        return self._head_tail(args, head=True)

    def cmd_tail(self, args: List[str]) -> str:
        return self._head_tail(args, head=False)

    def _head_tail(self, args: List[str], head: bool = True) -> str:
        n = 10
        clean = []
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try:
                    n = int(args[i+1])
                except ValueError:
                    return "invalid number for -n"
                i += 2
            else:
                clean.append(args[i])
                i += 1
        if not clean:
            return "missing file operand"
        node = self._get_abs(self._resolve(clean[0]))
        if node is None or node.type != "file":
            return f"{clean[0]}: No such file"
        lines = node.content.splitlines()
        selected = lines[:n] if head else lines[-n:]
        return "\n".join(selected)

    def _head_tail_stdin(self, args: List[str], stdin: str, head: bool = True) -> str:
        n = 10
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try:
                    n = int(args[i+1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        lines = stdin.splitlines()
        selected = lines[:n] if head else lines[-n:]
        return "\n".join(selected)

    def cmd_chmod(self, args: List[str]) -> str:
        clean = [a for a in args if not a.startswith("--")]
        if len(clean) != 2:
            return "chmod: expected mode and file"
        mode, path = clean
        node = self._get_abs(self._resolve(path))
        if node is None:
            return f"chmod: cannot access '{path}': No such file"
        if mode in ("+x", "755", "u+x", "a+x", "775"):
            node.executable = True
        elif mode in ("644", "600", "-x", "a-x"):
            node.executable = False
        return ""

    def cmd_ps(self, args: List[str]) -> str:
        return (
            "  PID TTY      STAT  COMMAND\n"
            "    1 ?        Ss    init\n"
            "  101 pts/0    S     bash\n"
            "  248 pts/0    R     python3 linuxx.py\n"
            "  404 ?        S     fake-nginx\n"
            "  512 ?        Sl    fake-postgres"
        )

    def cmd_kill(self, args: List[str]) -> str:
        if not args:
            return "kill: usage: kill [-signal] PID"
        pid = args[-1]
        if not pid.isdigit():
            return f"kill: {pid}: arguments must be process IDs"
        return f"[simulation] Process {pid} terminated."

    def cmd_history(self, args: List[str]) -> str:
        limit = len(self.command_log)
        if args and args[0].isdigit():
            limit = max(0, int(args[0]))
        start = max(0, len(self.command_log) - limit)
        rows = [
            f"{i:>5}  {cmd}"
            for i, cmd in enumerate(self.command_log[start:], start + 1)
        ]
        return "\n".join(rows)

    def add_xp(self, amount: int) -> Optional[int]:
        """Add XP and return new level if leveled up, else None."""
        old_level = self.level()
        self.xp += amount
        new_level = self.level()
        return new_level if new_level > old_level else None

    def level(self) -> int:
        lvl = 1
        for i, threshold in enumerate(XP_THRESHOLDS[1:], 2):
            if self.xp >= threshold:
                lvl = i
            else:
                break
        return lvl

    def xp_for_next(self) -> Tuple[int, int]:
        """Returns (current xp in this level, xp needed for next level)."""
        lvl = self.level()
        base = XP_THRESHOLDS[lvl - 1] if lvl - 1 < len(XP_THRESHOLDS) else XP_THRESHOLDS[-1]
        target = XP_THRESHOLDS[lvl] if lvl < len(XP_THRESHOLDS) else XP_THRESHOLDS[-1]
        return self.xp - base, max(target - base, 1)



# ─────────────────────────── Editors ───────────────────────────

class NanoEditor:
    """Simulated nano — line-by-line input, Ctrl sequences shown as text hints."""

    HELP = (
        "  ^O Write Out   ^X Exit   ^K Cut Line   ^U Paste   ^W Where Is"
    )

    def __init__(self, shell: "FakeShell", filepath: str):
        self.shell = shell
        self.filepath = filepath or "unnamed"
        node = shell._get_abs(shell._resolve(filepath)) if filepath else None
        self.lines: List[str] = (node.content.rstrip("\n").splitlines()
                                 if node and node.type == "file" else [])
        self.modified = False

    def run(self) -> str:
        """Return status message after editor closes."""
        UI.clear()
        self._draw()
        print(UI.c("\n  LINE EDITOR — type lines, blank line = new para.", UI.DIM))
        print(UI.c("  Commands:  :w  save    :q  quit    :wq  save+quit", UI.YELLOW))
        print(UI.c("             :d  delete last line    :p  print file", UI.YELLOW))
        print()
        while True:
            try:
                raw = input(UI.c("  nano> ", UI.CYAN))
            except (EOFError, KeyboardInterrupt):
                return "nano: exit without saving"
            if raw == ":wq":
                self._save()
                return f"nano: wrote {len(self.lines)} lines to {self.filepath}"
            elif raw == ":w":
                self._save()
                print(UI.c(f"  Saved to {self.filepath}", UI.GREEN))
                self.modified = False
            elif raw == ":q":
                if self.modified:
                    ans = input(UI.c("  Unsaved changes. Quit anyway? (y/n) > ", UI.YELLOW)).strip()
                    if ans.lower() != "y":
                        continue
                return "nano: quit"
            elif raw == ":d":
                if self.lines:
                    removed = self.lines.pop()
                    self.modified = True
                    print(UI.c(f"  Deleted: {removed!r}", UI.RED))
                else:
                    print(UI.c("  Buffer empty.", UI.DIM))
            elif raw == ":p":
                self._draw()
            elif raw.startswith(":"):
                print(UI.c(f"  Unknown command {raw!r}. Use :w :q :wq :d :p", UI.RED))
            else:
                self.lines.append(raw)
                self.modified = True

    def _save(self):
        parent, name = self.shell._parent_and_name(self.filepath)
        if parent and parent.type == "dir":
            parent.children[name] = Node("file", content="\n".join(self.lines) + "\n")

    def _draw(self):
        print(UI.c(f"  ┌── GNU nano ── {self.filepath} {'[Modified]' if self.modified else ''}", UI.BOLD + UI.CYAN))
        if self.lines:
            for i, line in enumerate(self.lines, 1):
                print(f"  {UI.c(str(i).rjust(3), UI.DIM)}  {line}")
        else:
            print(UI.c("  (empty file)", UI.DIM))
        print(UI.c(f"  └{'─'*60}", UI.CYAN))
        print(UI.c(NanoEditor.HELP, UI.DIM))


VIM_LESSONS: List["Lesson"] = []  # filled below after Lesson is defined

@dataclass
class VimStep:
    instruction: str
    accepted_keys: List[str]      # exact key sequences that satisfy this step
    hint: str
    explanation: str
    mode_after: str = "normal"    # which mode should be active after this step


class VimEditor:
    """
    Simulated vim — teaches modes interactively.
    mode: "normal" | "insert" | "command" | "visual"
    """

    STATUS_COLORS = {
        "normal":  UI.CYAN,
        "insert":  UI.GREEN,
        "command": UI.YELLOW,
        "visual":  UI.MAGENTA,
    }

    def __init__(self, shell: "FakeShell", filepath: str):
        self.shell   = shell
        self.filepath = filepath or "unnamed"
        node = shell._get_abs(shell._resolve(filepath)) if filepath else None
        self.lines: List[str] = (node.content.rstrip("\n").splitlines()
                                 if node and node.type == "file" else [])
        self.mode    = "normal"
        self.cursor  = 0          # line index
        self.col     = 0
        self.yanked  = ""
        self.modified = False
        self.cmd_buf = ""         # accumulated :command buffer

    def run(self) -> str:
        """Free-form vim session (used from sandbox/shell)."""
        self._draw()
        while True:
            try:
                raw = input(UI.c(f"  [{self.mode.upper()}] vim> ", self.STATUS_COLORS.get(self.mode, UI.WHITE)))
            except (EOFError, KeyboardInterrupt):
                return "vim: exit without saving"
            result = self._handle(raw)
            if result is not None:
                return result
            self._draw()

    def _handle(self, raw: str) -> Optional[str]:
        """Process one input line. Returns exit message or None to continue."""
        if self.mode == "normal":
            return self._normal(raw)
        elif self.mode == "insert":
            return self._insert(raw)
        elif self.mode == "command":
            return self._command(raw)
        elif self.mode == "visual":
            self.mode = "normal"
            return None
        return None

    def _normal(self, raw: str) -> Optional[str]:
        raw = raw.strip()
        if raw == "i":
            self.mode = "insert"
            print(UI.c("  -- INSERT --", UI.GREEN))
        elif raw == "I":
            self.col = 0; self.mode = "insert"
            print(UI.c("  -- INSERT -- (beginning of line)", UI.GREEN))
        elif raw == "a":
            self.col = min(self.col + 1, len(self._cur_line()))
            self.mode = "insert"
            print(UI.c("  -- INSERT -- (after cursor)", UI.GREEN))
        elif raw == "A":
            self.col = len(self._cur_line()); self.mode = "insert"
            print(UI.c("  -- INSERT -- (end of line)", UI.GREEN))
        elif raw == "o":
            self.lines.insert(self.cursor + 1, "")
            self.cursor += 1; self.col = 0
            self.mode = "insert"; self.modified = True
            print(UI.c("  -- INSERT -- (new line below)", UI.GREEN))
        elif raw == "O":
            self.lines.insert(self.cursor, "")
            self.col = 0; self.mode = "insert"; self.modified = True
            print(UI.c("  -- INSERT -- (new line above)", UI.GREEN))
        elif raw in ("j", "DOWN"):
            self.cursor = min(self.cursor + 1, max(len(self.lines) - 1, 0))
        elif raw in ("k", "UP"):
            self.cursor = max(self.cursor - 1, 0)
        elif raw in ("h", "LEFT"):
            self.col = max(self.col - 1, 0)
        elif raw in ("l", "RIGHT"):
            self.col = min(self.col + 1, len(self._cur_line()))
        elif raw == "G":
            self.cursor = max(len(self.lines) - 1, 0)
        elif raw == "gg":
            self.cursor = 0
        elif raw == "dd":
            if self.lines:
                self.yanked = self.lines.pop(self.cursor)
                self.cursor = min(self.cursor, max(len(self.lines) - 1, 0))
                self.modified = True
                print(UI.c(f"  1 line deleted (yanked)", UI.YELLOW))
        elif raw == "yy":
            self.yanked = self._cur_line()
            print(UI.c("  1 line yanked", UI.YELLOW))
        elif raw == "p":
            if self.yanked:
                self.lines.insert(self.cursor + 1, self.yanked)
                self.cursor += 1; self.modified = True
        elif raw == "P":
            if self.yanked:
                self.lines.insert(self.cursor, self.yanked)
                self.modified = True
        elif raw == "u":
            print(UI.c("  (undo not simulated — use :q! to abandon changes)", UI.DIM))
        elif raw == "v":
            self.mode = "visual"
            print(UI.c("  -- VISUAL -- (type any key to return to NORMAL)", UI.MAGENTA))
        elif raw == ":":
            self.mode = "command"
            print(UI.c("  :", UI.YELLOW), end="", flush=True)
        elif raw.startswith(":"):
            # convenience: full command typed at once
            self.mode = "command"
            return self._command(raw[1:])
        elif raw == "ZZ":
            self._save()
            return f"vim: wrote {len(self.lines)} lines to {self.filepath}"
        elif raw == "ZQ":
            return "vim: quit (no write)"
        elif raw in ("/", "?"):
            term = input(UI.c(f"  {raw}", UI.YELLOW))
            self._search(term)
        else:
            print(UI.c(f"  (unknown normal-mode key: {raw!r}  —  type i to insert, :wq to save)", UI.DIM))
        return None

    def _insert(self, raw: str) -> Optional[str]:
        if raw == "ESC" or raw == "\x1b":
            self.mode = "normal"
            print(UI.c("  -- NORMAL --", UI.CYAN))
            return None
        # typing in insert mode appends to current line
        if self.cursor >= len(self.lines):
            self.lines.append("")
        if raw == "":
            # blank Enter = new line
            self.lines.insert(self.cursor + 1, "")
            self.cursor += 1; self.col = 0
        else:
            self.lines[self.cursor] = self.lines[self.cursor] + raw
        self.modified = True
        return None

    def _command(self, raw: str) -> Optional[str]:
        raw = raw.strip()
        self.mode = "normal"
        if raw in ("w", "write"):
            self._save()
            print(UI.c(f"  \"{self.filepath}\" {len(self.lines)}L written", UI.GREEN))
        elif raw in ("q", "quit"):
            if self.modified:
                print(UI.c("  E37: No write since last change (add ! to override)", UI.RED))
            else:
                return "vim: quit"
        elif raw in ("q!", "quit!"):
            return "vim: quit (forced)"
        elif raw in ("wq", "x", "wq!", "x!"):
            self._save()
            return f"vim: wrote {len(self.lines)} lines to {self.filepath}"
        elif raw.startswith("w "):
            new_path = raw[2:].strip()
            old = self.filepath; self.filepath = new_path
            self._save(); self.filepath = old
            print(UI.c(f"  wrote to {new_path}", UI.GREEN))
        elif raw.startswith("%s/"):
            self._substitute(raw)
        elif raw == "set number" or raw == "set nu":
            print(UI.c("  (line numbers always shown in this sim)", UI.DIM))
        elif raw.isdigit():
            target = int(raw) - 1
            self.cursor = max(0, min(target, len(self.lines) - 1))
        else:
            print(UI.c(f"  E492: Not an editor command: {raw!r}", UI.RED))
        return None

    def _substitute(self, cmd: str):
        # :s/old/new/[g]  or  :%s/old/new/[g]
        parts = cmd.lstrip("%s").lstrip("s").split("/")
        if len(parts) < 3:
            print(UI.c("  substitute: bad syntax. Use %s/old/new/g", UI.RED))
            return
        _, old, new = parts[0], parts[1], parts[2]
        flags = parts[3] if len(parts) > 3 else ""
        count = 0
        global_sub = "g" in flags or cmd.startswith("%")
        range_all  = cmd.startswith("%")
        target_lines = range(len(self.lines)) if range_all else range(self.cursor, self.cursor + 1)
        for i in target_lines:
            line = self.lines[i]
            if global_sub:
                new_line = line.replace(old, new)
            else:
                new_line = line.replace(old, new, 1)
            if new_line != line:
                self.lines[i] = new_line
                count += 1
                self.modified = True
        print(UI.c(f"  {count} substitution(s)", UI.GREEN) if count else UI.c("  Pattern not found", UI.YELLOW))

    def _search(self, term: str):
        for i, line in enumerate(self.lines):
            if term in line:
                self.cursor = i
                print(UI.c(f"  Found on line {i+1}", UI.GREEN))
                return
        print(UI.c(f"  Pattern not found: {term!r}", UI.YELLOW))

    def _save(self):
        parent, name = self.shell._parent_and_name(self.filepath)
        if parent and parent.type == "dir":
            parent.children[name] = Node("file", content="\n".join(self.lines) + "\n")
            self.modified = False

    def _cur_line(self) -> str:
        if not self.lines:
            return ""
        return self.lines[min(self.cursor, len(self.lines) - 1)]

    def _draw(self):
        UI.clear()
        w = min(UI.width(), 100)
        print(UI.c(f"  {'─'*w}", UI.DIM))
        if not self.lines:
            print(UI.c("  ~  (empty buffer)", UI.DIM))
        else:
            for i, line in enumerate(self.lines):
                marker = UI.c("▶ ", UI.YELLOW) if i == self.cursor else "  "
                num = UI.c(str(i+1).rjust(3), UI.DIM)
                print(f"  {num} {marker}{line}")
        print(UI.c(f"  {'─'*w}", UI.DIM))
        mode_label = f"-- {self.mode.upper()} --"
        mod_flag   = UI.c(" [+]", UI.RED) if self.modified else ""
        print(UI.c(f"  {mode_label}", self.STATUS_COLORS.get(self.mode, UI.WHITE)) +
              UI.c(f"  {self.filepath}", UI.BOLD) + mod_flag +
              UI.c(f"  {len(self.lines)}L  ln:{self.cursor+1}", UI.DIM))
        print(UI.c("  i=insert  ESC=normal  :wq=save+quit  :q!=force quit  hjkl=move  dd=delete  yy=yank  p=paste", UI.DIM))


# ─────────────────────────── Progress Persistence ───────────────────────────

def node_to_dict(node: Node) -> Dict[str, Any]:
    return {
        "type": node.type,
        "content": node.content,
        "executable": node.executable,
        "children": {name: node_to_dict(child) for name, child in node.children.items()},
    }


def node_from_dict(data: Dict[str, Any]) -> Node:
    node = Node(
        data.get("type", "file"),
        content=data.get("content", ""),
        executable=bool(data.get("executable", False)),
    )
    children = data.get("children", {})
    if isinstance(children, dict):
        node.children = {
            name: node_from_dict(child)
            for name, child in children.items()
            if isinstance(child, dict)
        }
    return node


def save_progress(shell: FakeShell, quiz_answered: set) -> None:
    data = {
        "xp": shell.xp,
        "score": shell.score,
        "completed": list(shell.completed),
        "commands_run": shell.commands_run,
        "accomplished_commands": shell.accomplished_commands,
        "command_log": shell.command_log[-200:],
        "quiz_answered": list(quiz_answered),
        "streak": shell.streak,
        "filesystem": node_to_dict(shell.root),
        "cwd": shell.cwd,
        "prev_cwd": shell.prev_cwd,
    }
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def load_progress(shell: FakeShell, quiz_answered: set) -> None:
    try:
        if not os.path.exists(SAVE_FILE):
            return
        with open(SAVE_FILE) as f:
            data = json.load(f)
        shell.xp = data.get("xp", 0)
        shell.score = data.get("score", 0)
        shell.completed = set(data.get("completed", []))
        shell.commands_run = data.get("commands_run", 0)
        shell.accomplished_commands = data.get("accomplished_commands", [])
        shell.command_log = data.get("command_log", [])
        shell.streak = data.get("streak", 0)
        filesystem = data.get("filesystem")
        if isinstance(filesystem, dict):
            shell.root = node_from_dict(filesystem)
            cwd = data.get("cwd", ["home", "student"])
            if isinstance(cwd, list) and shell._get_abs(cwd) and shell._get_abs(cwd).type == "dir":
                shell.cwd = [str(part) for part in cwd]
            prev_cwd = data.get("prev_cwd")
            if isinstance(prev_cwd, list) and shell._get_abs(prev_cwd) and shell._get_abs(prev_cwd).type == "dir":
                shell.prev_cwd = [str(part) for part in prev_cwd]
            else:
                shell.prev_cwd = None
        quiz_answered.update(data.get("quiz_answered", []))
    except Exception:
        pass


# ─────────────────────────── App ───────────────────────────


# ─────────────────── Shared engine helpers (ex-TrainerApp) ──────────
# Command matcher + vim curriculum live at module level so both the TUI
# and tests use them without the classic CLI.

def _normalize_cmd(cmd: str) -> str:
    return " ".join(cmd.strip().split())


def _simple_command_signature(tokens: List[str]) -> Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...], Tuple[str, ...]]:
    value_options = {"-n", "-name", "-type"}
    cmd = tokens[0]
    flags: List[str] = []
    option_pairs: List[Tuple[str, str]] = []
    operands: List[str] = []
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in value_options and i + 1 < len(tokens):
            option_pairs.append((token, tokens[i + 1]))
            i += 2
        elif token.startswith("--") and len(token) > 2:
            flags.append(token)
            i += 1
        elif token.startswith("-") and len(token) > 1:
            flags.extend(f"-{char}" for char in token[1:])
            i += 1
        else:
            operands.append(token)
            i += 1
    return cmd, tuple(sorted(flags)), tuple(sorted(option_pairs)), tuple(operands)


def _command_signature(cmd: str) -> Optional[Tuple[Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...], Tuple[str, ...]], ...]]:
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars="|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    if not tokens:
        return None
    segments: List[List[str]] = [[]]
    for token in tokens:
        if token == "|":
            segments.append([])
        else:
            segments[-1].append(token)
    if any(not segment for segment in segments):
        return None
    return tuple(_simple_command_signature(segment) for segment in segments)


def engine_command_matches(raw: str, accepted_commands: List[str]) -> bool:
    raw_norm = _normalize_cmd(raw)
    accepted_norm = [_normalize_cmd(cmd) for cmd in accepted_commands]
    if raw_norm in accepted_norm:
        return True
    raw_sig = _command_signature(raw)
    if raw_sig is None:
        return False
    return any(raw_sig == _command_signature(cmd) for cmd in accepted_commands)


def engine_mission_key(lesson, mission) -> str:
    return f"{lesson.command}:{mission.prompt}"


VIM_STEPS = [
    VimStep(
        "You're in NORMAL mode. Press  i  to enter INSERT mode.",
        ["i"],
        "In vim, you always start in NORMAL mode. 'i' switches to INSERT.",
        "vim has modes. NORMAL is for navigation/commands. INSERT is for typing text.",
        mode_after="insert",
    ),
    VimStep(
        "You're in INSERT mode. Type a line of text, then press  ESC  to return to NORMAL.",
        ["ESC"],
        "Type anything, then type ESC to leave INSERT mode.",
        "ESC is how you leave INSERT mode. This is the most important vim key.",
        mode_after="normal",
    ),
    VimStep(
        "In NORMAL mode, press  o  to open a new line below and enter INSERT.",
        ["o"],
        "'o' = open line below. One of the most-used vim commands.",
        "'o' creates a blank line below the cursor and drops you into INSERT.",
        mode_after="insert",
    ),
    VimStep(
        "Press  ESC  to return to NORMAL mode.",
        ["ESC"],
        "Always ESC to get back to NORMAL.",
        "If you're ever lost in vim, spam ESC until you're in NORMAL mode.",
        mode_after="normal",
    ),
    VimStep(
        "Navigate with  j  (down) and  k  (up). Press  j  now.",
        ["j"],
        "j = down, k = up, h = left, l = right.",
        "hjkl are the vim navigation keys — designed so your fingers never leave home row.",
        mode_after="normal",
    ),
    VimStep(
        "Press  k  to move up.",
        ["k"],
        "k moves up one line.",
        "j/k replace the arrow keys in vim. Faster once memorised.",
        mode_after="normal",
    ),
    VimStep(
        "Press  dd  to delete the current line.",
        ["dd"],
        "dd deletes the whole line and puts it in the buffer.",
        "dd = delete line. The deleted line is also yanked (buffered) for pasting.",
        mode_after="normal",
    ),
    VimStep(
        "Press  p  to paste the deleted line back below the cursor.",
        ["p"],
        "p pastes whatever was last yanked/deleted.",
        "p = put. It inserts the buffer below the current line.",
        mode_after="normal",
    ),
    VimStep(
        "Press  yy  to yank (copy) the current line without deleting it.",
        ["yy"],
        "yy = yank line. Think 'y' for yoink.",
        "yy copies the line into the buffer. p to paste it.",
        mode_after="normal",
    ),
    VimStep(
        "Type  :  to enter COMMAND mode, then type  w  and press Enter to save.",
        [":w", "w"],
        "':' opens the command line at the bottom. 'w' = write (save).",
        ":w saves the file. The colon prompt appears at the bottom of the screen.",
        mode_after="normal",
    ),
    VimStep(
        "Type  :%s/linux/LINUX/g  to replace every occurrence of 'linux' with 'LINUX'.",
        [":%s/linux/LINUX/g"],
        "%s/old/new/g replaces all. % = whole file, g = all on each line.",
        ":%s is vim's substitute command. One of the most powerful editing tools.",
        mode_after="normal",
    ),
    VimStep(
        "Type  :wq  to save and quit vim.",
        [":wq", "wq"],
        ":wq = write + quit. The standard vim exit.",
        ":wq saves and closes the file. You've completed the vim basics!",
        mode_after="normal",
    ),
]

# ─────────────────────────── TUI (single-file) ───────────────────────────
# Full Textual TUI lives here — linuxx.py is the single file.
# Engine + --test work with NO extra deps; textual is optional (TUI only).

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import (
        Header, Input, Label, ListItem, ListView,
        RichLog, Static, ProgressBar, Button, TextArea,
    )
    _TEXTUAL_AVAILABLE = True
    _TEXTUAL_ERROR = None
except ImportError as _tui_import_error:  # textual not installed
    App = object  # type: ignore
    ComposeResult = object  # type: ignore
    Horizontal = Vertical = object  # type: ignore
    ModalScreen = object  # type: ignore
    Header = Input = Label = ListItem = ListView = object  # type: ignore
    RichLog = Static = ProgressBar = Button = TextArea = object  # type: ignore
    _TEXTUAL_AVAILABLE = False
    _TEXTUAL_ERROR = _tui_import_error


def _tui_normalize(cmd: str) -> str:
    return " ".join(cmd.strip().split())


def tui_command_matches(raw: str, accepted: List[str]) -> bool:
    # Battle-tested matcher (flag order, quoting, pipes).
    return engine_command_matches(raw, accepted)


# Alias kept for external callers that used command_matches.
def command_matches(raw: str, accepted: List[str]) -> bool:
    return tui_command_matches(raw, accepted)


TUI_LEVEL_BADGES = {1: "🐣", 2: "🌱", 3: "⚡", 4: "🔥", 5: "💎", 6: "👑", 7: "🦾", 8: "🚀", 9: "🌌", 10: "🏆"}


def tui_level_badge(level: int) -> str:
    return TUI_LEVEL_BADGES.get(min(level, 10), "🏆")


def tui_mission_key(lesson, mission) -> str:
    return f"{lesson.command}:{mission.prompt}"


# Alias kept for external callers that used mission_key.
def mission_key(lesson, mission) -> str:
    return tui_mission_key(lesson, mission)


if _TEXTUAL_AVAILABLE:

    class StatsBar(Static):
        def compose(self) -> ComposeResult:
            yield Label(id="stats_line1")
            yield ProgressBar(total=100, show_eta=False, id="xp_bar")
            yield Label(id="stats_line2")

        def refresh_display(self, shell: FakeShell) -> None:
            lvl = shell.level()
            xp_cur, xp_max = shell.xp_for_next()
            total = sum(len(les.missions) for les in LESSONS)
            done = len(shell.completed)
            self.query_one("#stats_line1", Label).update(
                f"{tui_level_badge(lvl)} Level {lvl}  ·  {done} of {total} goals done  ·  You are here: {shell.pwd()}  ·  Score {shell.score}"
            )
            bar = self.query_one("#xp_bar", ProgressBar)
            bar.update(total=xp_max, progress=xp_cur)
            self.query_one("#stats_line2", Label).update(
                f"Safe playground — nothing real can break. {getattr(self, 'tip', '')}"
            )


    class LessonDetail(Static):
        def compose(self) -> ComposeResult:
            yield Label("", id="detail_title")
            yield Label("", id="detail_mission")

        def show_lesson(self, idx: int, shell: FakeShell) -> None:
            lesson = LESSONS[idx]
            done_missions = sum(1 for m in lesson.missions if tui_mission_key(lesson, m) in shell.completed)
            current = next((m for m in lesson.missions if tui_mission_key(lesson, m) not in shell.completed), None)
            mark = "done ✓" if done_missions == len(lesson.missions) else f"{done_missions}/{len(lesson.missions)} done"
            self.query_one("#detail_title", Label).update(f"{lesson.command} — {lesson.title} ({mark})")
            if current:
                self.query_one("#detail_mission", Label).update(
                    f"Your goal: {current.prompt}  →  Try typing: {current.accepted[0]}  (F2 fills it in)"
                )
            else:
                self.query_one("#detail_mission", Label).update("All done here — pick the next lesson below.")


    class CaptoPane(Static):
        def compose(self) -> ComposeResult:
            yield Label("Hi! I'm Capto82 — your guide. You can't break anything here.", id="capto_line")

        def say(self, text: str) -> None:
            self.query_one("#capto_line", Label).update(f"🦊 Capto82: {text}")


    class WelcomeScreen(ModalScreen):
        CSS = """
        WelcomeScreen { align: center middle; }
        #welcome_box { border: round #7ee787; background: #0d1526; padding: 1 3; width: 62; height: auto; }
        #welcome_title { text-style: bold; color: #7ee787; height: 1; }
        #welcome_body { color: #c9d1d9; height: auto; margin-top: 1; }
        #welcome_btns { height: 3; margin-top: 1; }
        Button { margin-right: 1; }
        """

        def compose(self) -> ComposeResult:
            with Vertical(id="welcome_box"):
                yield Label("🌱 Welcome to LNXX — your safe terminal playground", id="welcome_title")
                yield Label(
                    "Never touched a terminal? Perfect — you're who this is for.\n\n"
                    "• This is a PRETEND computer. No real files. No way to break anything.\n"
                    "• Your first win takes ~30 seconds: type one tiny word, press Enter.\n"
                    "• Stuck? F1 hint, F2 fills the answer, F3 full lesson, F4 missions,\n"
                    "  F6 speed challenge, F7 cheat+record, F8 vim dojo. Capto82 never judges.",
                    id="welcome_body",
                )
                with Horizontal(id="welcome_btns"):
                    yield Button("Start my first win (recommended)", id="go", variant="success")
                    yield Button("Explore freely", id="free")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(event.button.id)


    class QuizScreen(ModalScreen):
        BINDINGS = [("escape", "skip", "Skip quiz")]
        CSS = """
        QuizScreen { align: center middle; }
        #quiz_box { border: round #ffd479; background: #17142e; padding: 1 3; width: 64; height: auto; }
        #quiz_title { text-style: bold; color: #ffd479; height: 1; }
        #quiz_q { color: #e6ebf2; height: auto; margin-top: 1; }
        #quiz_input { margin-top: 1; }
        """

        def __init__(self, lesson_idx: int):
            super().__init__()
            self.lesson_idx = lesson_idx
            lesson = LESSONS[lesson_idx]
            self.quiz = QUIZ_QUESTIONS.get(lesson.command)

        def compose(self) -> ComposeResult:
            lesson = LESSONS[self.lesson_idx]
            with Vertical(id="quiz_box"):
                yield Label(f"Capto checkpoint — {lesson.command}", id="quiz_title")
                yield Label(self.quiz["q"] if self.quiz else "No quiz.", id="quiz_q")
                yield Input(placeholder="Answer in plain words, Enter to check · Esc to skip", id="quiz_input")

        def on_mount(self) -> None:
            self.query_one("#quiz_input", Input).focus()

        def action_skip(self) -> None:
            self.dismiss(None)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            self.dismiss(event.value.strip())


    class NanoScreen(ModalScreen):
        BINDINGS = [("escape", "cancel", "Quit")]
        CSS = """
        NanoScreen { align: center middle; }
        #nano_box { border: round #58a6ff; background: #0d1526; padding: 1 2; width: 72; height: 24; }
        #nano_title { text-style: bold; color: #58a6ff; height: 1; }
        #nano_area { height: 1fr; margin-top: 1; }
        #nano_btns { height: 3; margin-top: 1; }
        """

        def __init__(self, shell: FakeShell, path: str):
            super().__init__()
            self.shell = shell
            self.path = path or "unnamed"
            node = shell._get_abs(shell._resolve(path)) if path else None
            self.start_text = node.content if node and node.type == "file" else ""

        def compose(self) -> ComposeResult:
            with Vertical(id="nano_box"):
                yield Label(f"nano — {self.path}  (edit freely, nothing real)", id="nano_title")
                yield TextArea(self.start_text, id="nano_area")
                with Horizontal(id="nano_btns"):
                    yield Button("Save + close", id="save", variant="success")
                    yield Button("Quit without saving", id="quit")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "save":
                text = self.query_one("#nano_area", TextArea).text
                if not text.endswith("\n") and text:
                    text += "\n"
                parent, name = self.shell._parent_and_name(self.path)
                if parent and parent.type == "dir":
                    parent.children[name] = Node("file", content=text)
                self.dismiss(f"nano: wrote to {self.path}")
            else:
                self.dismiss("nano: quit")

        def action_cancel(self) -> None:
            self.dismiss("nano: quit")


    class VimScreen(ModalScreen):
        BINDINGS = [("escape", "cancel", "Quit")]
        CSS = """
        VimScreen { align: center middle; }
        #vim_box { border: round #a371f7; background: #0d1526; padding: 1 2; width: 72; height: 26; }
        #vim_title { text-style: bold; color: #a371f7; height: 1; }
        #vim_status { color: #ffd479; height: 1; margin-top: 1; }
        #vim_keys { margin-top: 1; }
        """

        def __init__(self, shell: FakeShell, path: str, steps=None):
            super().__init__()
            self.shell = shell
            self.path = path or "workshop.txt"
            node = shell._get_abs(shell._resolve(path)) if path else None
            self.start_text = node.content if node and node.type == "file" else ""
            self.vim = VimEditor(shell, path)
            self.steps = steps  # None = free edit; list = workshop
            self.step_idx = 0

        def compose(self) -> ComposeResult:
            with Vertical(id="vim_box"):
                yield Label(f"vim — {self.path}  (modes: NORMAL/INSERT/COMMAND)", id="vim_title")
                yield TextArea(self.start_text, id="vim_area")
                yield Label("-- NORMAL --  i=insert ESC=normal :wq=save+quit", id="vim_status")
                yield Input(placeholder="vim keys: i · ESC · dd · yy · p · :w · :wq · :q!   (Enter sends)", id="vim_keys")

        def on_mount(self) -> None:
            self.query_one("#vim_keys", Input).focus()
            if self.steps:
                self._show_step()

        def action_cancel(self) -> None:
            self.dismiss("vim: quit")

        def _show_step(self) -> None:
            step = self.steps[self.step_idx]
            self.query_one("#vim_status", Label).update(
                f"Step {self.step_idx+1}/{len(self.steps)} [{self.vim.mode.upper()}] {step.instruction}"
            )

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw = event.value.strip()
            event.input.value = ""
            if raw == "back":
                self.dismiss("vim: quit")
                return
            result = self.vim._handle(raw)
            # reflect editor buffer into textarea
            area = self.query_one("#vim_area", TextArea)
            area.clear()
            area.insert("\n".join(self.vim.lines))
            if self.steps:
                step = self.steps[self.step_idx]
                accepted = [k.lstrip(":").strip() for k in step.accepted_keys]
                if raw.lstrip(":").strip() in accepted or raw in step.accepted_keys:
                    self.step_idx += 1
                    if self.step_idx >= len(self.steps):
                        self.vim._save()
                        self.dismiss(f"workshop complete|{step.explanation}")
                        return
                    self.vim.mode = step.mode_after
                    self._show_step()
                else:
                    self.query_one("#vim_status", Label).update(
                        f"Expected {step.accepted_keys[0]} — hint: {step.hint}"
                    )
                    return
            else:
                self.query_one("#vim_status", Label).update(
                    f"-- {self.vim.mode.upper()} --  {len(self.vim.lines)}L" + (" [+]" if self.vim.modified else "")
                )
            if result is not None:
                self.dismiss(result)


    class LNXXApp(App):
        CSS = """
        Screen { background: #101623; }
        #banner { color: #ffd479; text-style: bold; padding: 0 2; height: 1; }
        #track_bar { color: #9aa4b2; padding: 0 2; height: 1; }
        StatsBar { border: round #30363d; padding: 0 2; margin: 0 2; height: 4; color: #e6ebf2; background: #131b2e; }
        #xp_bar { height: 1; margin: 0; }
        #stats_line1 { height: 1; }
        #stats_line2 { height: 1; color: #ffd479; }
        #body { margin: 0 2; height: 1fr; }
        #lesson_list { border: round #30363d; border-title-align: left; width: 24; background: #131b2e; min-height: 8; }
        #lesson_list:focus { border: round #ffd479; }
        ListItem { padding: 0 1; height: 1; }
        ListItem.-done Label { color: #7ee787; }
        ListItem.-next Label { color: #ffd479; text-style: bold; }
        #mid { width: 1fr; margin-left: 1; }
        LessonDetail { border: round #30363d; padding: 0 2; height: 4; background: #131b2e; }
        #detail_title { text-style: bold; color: #8ad0ff; height: 1; }
        #detail_mission { color: #b8f0c0; height: 2; }
        #term_log { border: round #7ee787; border-title-align: left; height: 1fr; min-height: 6; margin-top: 1; background: #0a0f1c; color: #e6ebf2; }
        #term_input { margin-top: 1; height: 3; }
        #term_input:focus { border: round #ffd479; }
        CaptoPane { border: round #a371f7; padding: 0 2; margin-top: 1; height: 3; color: #e6ebf2; background: #17142e; }
        """
        BINDINGS = [
            ("q", "quit", "Quit"),
            ("ctrl+k", "focus_lessons", "Lessons"),
            ("ctrl+j", "focus_term", "Terminal"),
            ("f1", "hint", "Hint"),
            ("f2", "fill_answer", "Fill answer"),
            ("f3", "learn_card", "Full lesson"),
            ("f4", "missions", "Missions"),
            ("f5", "cheat", "Cheat"),
            ("f6", "challenge", "Challenge"),
            ("f7", "record", "Record"),
            ("f8", "vim_dojo", "Vim dojo"),
            ("f9", "reset_all", "Reset"),
        ]
        TITLE = "LNXX"

        def __init__(self):
            super().__init__()
            self.shell = FakeShell()
            self.quiz_answered: set = set()
            self.active_lesson = 0
            self.challenge: Optional[Dict] = None
            self.vim_dojo: Optional[Dict] = None
            load_progress(self.shell, self.quiz_answered)

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Label("🌱 LNXX · your safe terminal playground — nothing real can break", id="banner")
            yield Label("F1 hint · F2 fill · F3 lesson · F4 missions · F6 challenge · F7 cheat+record · F8 vim · F9 reset", id="track_bar", markup=False)
            yield StatsBar()
            with Horizontal(id="body"):
                yield ListView(
                    *[ListItem(Label(f"{les.command:<10}"), name=str(i)) for i, les in enumerate(LESSONS)],
                    id="lesson_list",
                )
                with Vertical(id="mid"):
                    yield LessonDetail()
                    yield RichLog(id="term_log", wrap=True, markup=True)
                    yield Input(placeholder="Type pwd here and press Enter — nothing can break ✨ (F2 fills it in)", id="term_input")
                    yield CaptoPane()

        # ── mount / nav ──

        def on_mount(self) -> None:
            stats = self.query_one(StatsBar)
            stats.tip = random.choice(TIPS_OF_THE_DAY)
            stats.refresh_display(self.shell)
            lv = self.query_one("#lesson_list", ListView)
            lv.border_title = "YOUR LESSONS — start at the top"
            log = self.query_one(RichLog)
            log.border_title = "TERMINAL — every mode lives here"
            self.query_one(CaptoPane).border_title = "CAPTO82, YOUR GUIDE"
            self._sync_lesson(self._first_unfinished(), announce=True)
            lv.index = self.active_lesson
            log.write("[bold]How this works (30 seconds):[/]")
            log.write("1. Goal above (e.g. “Show your current folder”). 2. Type below + Enter.")
            log.write("[dim]F1 hint · F2 fill · F3 full lesson · F4 all missions · F6 speed challenge · F7 cheat+record · F8 vim dojo · nano/vim <file> open editors[/]")
            self.query_one("#term_input", Input).focus()
            if not self.shell.completed and self.shell.xp == 0:
                self.push_screen(WelcomeScreen(), self._welcome_done)

        def _welcome_done(self, choice: Optional[str]) -> None:
            if choice == "go":
                self._sync_lesson(0, announce=True)
                self.query_one("#lesson_list", ListView).index = 0
                self.action_fill_answer()
                self.query_one(RichLog).write("[yellow]I filled in your first answer — just press Enter. ✨[/]")
            self.query_one("#term_input", Input).focus()

        def _first_unfinished(self) -> int:
            for i, les in enumerate(LESSONS):
                if not all(tui_mission_key(les, m) in self.shell.completed for m in les.missions):
                    return i
            return 0

        def _sync_lesson(self, idx: int, announce: bool = False) -> None:
            self.active_lesson = idx
            lesson = LESSONS[idx]
            self.query_one(LessonDetail).show_lesson(idx, self.shell)
            if announce:
                first = lesson.missions[0].prompt if lesson.missions else lesson.title
                self.query_one(CaptoPane).say(f"You're on {lesson.command} — {first} I'm here if you wobble.")
            lv = self.query_one("#lesson_list", ListView)
            first_open = self._first_unfinished()
            for i, les in enumerate(LESSONS):
                done = all(tui_mission_key(les, m) in self.shell.completed for m in les.missions)
                try:
                    item = lv.children[i]
                    item.set_class(done, "-done")
                    item.set_class(i == first_open and not done, "-next")
                    prefix = "✓ " if done else ("👉 " if i == first_open else "   ")
                    item.query_one(Label).update(f"{prefix}{les.command:<10}")
                except Exception:
                    pass

        def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
            if event.item is not None:
                self._sync_lesson(int(event.item.name), announce=True)

        def action_focus_lessons(self) -> None:
            self.query_one("#lesson_list", ListView).focus()

        def action_focus_term(self) -> None:
            self.query_one("#term_input", Input).focus()

        # ── F3 full lesson card (Learn) ──

        def action_learn_card(self) -> None:
            les = LESSONS[self.active_lesson]
            log = self.query_one(RichLog)
            log.write(f"[bold cyan]══ {les.title} ({les.command}) ══[/]")
            log.write(f"[bold]Idea:[/] {les.concept}")
            log.write(f"[yellow]How: {les.syntax}[/]")
            log.write("[green]Try:[/]")
            for ex in les.examples:
                log.write(f"  $ {ex}")
            log.write("[yellow]Watch out:[/]")
            for m in les.mistakes:
                log.write(f"  ✗ {m}")
            if les.pro_tip:
                log.write(f"[magenta]⚡ Pro tip: {les.pro_tip}[/]")
            self.query_one(CaptoPane).say(f"{les.command}: read the card above, then try it below. F2 fills it in.")

        # ── F4 missions list (Practice) ──

        def action_missions(self) -> None:
            log = self.query_one(RichLog)
            log.write("[bold cyan]══ PRACTICE MISSIONS — type any command below, credit finds its lesson ══[/]")
            flat = [(l, m) for l in LESSONS for m in l.missions]
            for i, (les, m) in enumerate(flat, 1):
                done = "✓" if tui_mission_key(les, m) in self.shell.completed else "○"
                log.write(f"  {done} {i:>2}. [{les.command}] {m.prompt} (+{m.xp})")
            log.write("[dim]Just type the command in the terminal — e.g. the first open ○ line. F1/F2 help.[/]")
            self.query_one(CaptoPane).say("Every mission, one list. Type any — I'll credit the right lesson.")

        def action_cheat(self) -> None:
            log = self.query_one(RichLog)
            log.write("[bold cyan]══ CHEAT SHEET ══[/]")
            for les in LESSONS:
                log.write(f"[green]{les.command:<12}[/] [yellow]{les.syntax}[/]  {les.title}")
            log.write("[cyan]Pipes: cmd1 | cmd2 · Redirect: > overwrite, >> append · !! repeat · help · history[/]")

        # ── F7 record ──

        def action_record(self) -> None:
            s = self.shell
            lvl = s.level()
            cur, mx = s.xp_for_next()
            total = sum(len(les.missions) for les in LESSONS)
            log = self.query_one(RichLog)
            log.write("[bold cyan]══ COMMAND RECORD ══[/]")
            log.write(f"Level {lvl} {tui_level_badge(lvl)} · XP {s.xp} ({cur}/{mx}) · Score {s.score} · Goals {len(s.completed)}/{total} · Cmds {s.commands_run} · Quiz {len(self.quiz_answered)}")
            log.write("[green]Your winning commands:[/]")
            for i, c in enumerate(s.accomplished_commands[-10:], 1):
                log.write(f"  {i}. {c}")
            log.write("[yellow]Recent:[/]")
            for c in s.command_log[-8:]:
                log.write(f"  · {c}")

        # ── F6 speed challenge ──

        def action_challenge(self) -> None:
            flat = [(l, m) for l in LESSONS for m in l.missions]
            pool = [p for p in flat if tui_mission_key(*p) not in self.shell.completed] or flat
            selected = random.sample(pool, min(5, len(pool)))
            self.challenge = {"items": selected, "idx": 0, "xp": 0, "t0": time.time()}
            log = self.query_one(RichLog)
            log.write("[bold cyan]══ SPEED CHALLENGE — 5 goals, bonus for speed. Type 'skip' to skip. ══[/]")
            self._challenge_prompt()

        def _challenge_prompt(self) -> None:
            ch = self.challenge
            if not ch or ch["idx"] >= len(ch["items"]):
                return
            les, m = ch["items"][ch["idx"]]
            ch["t0"] = time.time()
            self.query_one(RichLog).write(f"[bold]Challenge {ch['idx']+1}/{len(ch['items'])} [{les.command}]: {m.prompt}[/]")
            self.query_one(CaptoPane).say("Clock's on — fast and calm. Skip anytime.")

        def _challenge_answer(self, raw: str) -> bool:
            ch = self.challenge
            if not ch or ch["idx"] >= len(ch["items"]):
                return False
            if raw == "skip":
                les, m = ch["items"][ch["idx"]]
                self.query_one(RichLog).write(f"[yellow]Skipped — one answer: {m.accepted[0]}[/]")
                ch["idx"] += 1
                if ch["idx"] >= len(ch["items"]):
                    self._challenge_finish()
                else:
                    self._challenge_prompt()
                return True
            les, m = ch["items"][ch["idx"]]
            if tui_command_matches(raw, m.accepted):
                elapsed = time.time() - ch["t0"]
                bonus = 10 if elapsed < 5 else (5 if elapsed < 10 else 0)
                gain = m.xp + bonus
                ch["xp"] += gain
                self.shell.completed.add(tui_mission_key(les, m))
                new_lvl = self.shell.add_xp(gain)
                self.shell.score += gain
                self.query_one(RichLog).write(f"[green]✓ +{gain} XP ({elapsed:.1f}s)[/] {random.choice(AFFIRMATIONS)}")
                if new_lvl:
                    self.query_one(RichLog).write(f"[bold yellow]★ Level {new_lvl}[/]")
                ch["idx"] += 1
                if ch["idx"] >= len(ch["items"]):
                    self._challenge_finish()
                else:
                    self._challenge_prompt()
                self._refresh()
                return True
            return False

        def _challenge_finish(self) -> None:
            ch = self.challenge
            total = ch["xp"] if ch else 0
            self.query_one(RichLog).write(f"[bold green]Challenge done: +{total} XP total.[/]")
            self.query_one(CaptoPane).say("Speed + accuracy — that's operator energy.")
            self.challenge = None
            self._refresh()

        # ── F8 vim dojo ──

        def action_vim_dojo(self) -> None:
            steps = VIM_STEPS
            self.shell._write_abs(self.shell.cwd + ["workshop.txt"], "linux is a kernel\npractice makes permanent\nvim is worth the pain\n")
            self.push_screen(VimScreen(self.shell, "workshop.txt", steps=steps), self._vim_done)

        def _vim_done(self, result: Optional[str]) -> None:
            log = self.query_one(RichLog)
            if result and result.startswith("workshop complete"):
                gain = 8 * len(VIM_STEPS)
                new_lvl = self.shell.add_xp(gain)
                self.shell.score += gain
                self.shell.accomplished_commands.append("vim workshop")
                log.write(f"[bold green]Vim dojo complete: +{gain} XP.[/] :%s/old/new/g is now yours.")
                log.write("[magenta]i/a/o insert · ESC normal · :wq save+quit · dd cut · yy copy · p paste · hjkl move[/]")
                if new_lvl:
                    log.write(f"[bold yellow]★ Level {new_lvl}[/]")
                self.query_one(CaptoPane).say("Vim modes: conquered. That editor fears YOU now.")
            elif result:
                log.write(f"[dim]{result}[/]")
            self._refresh()
            self.query_one("#term_input", Input).focus()

        # ── F9 reset ──

        def action_reset_all(self) -> None:
            self.push_screen(ResetScreen(), self._reset_done)

        def _reset_done(self, choice: Optional[str]) -> None:
            if choice == "yes":
                self.shell = FakeShell()
                self.quiz_answered.clear()
                try:
                    if os.path.exists(SAVE_FILE):
                        os.remove(SAVE_FILE)
                except Exception:
                    pass
                self.query_one(RichLog).write("[green]Fresh start — playground rebuilt, progress cleared. 🌱[/]")
                self.query_one(CaptoPane).say("Clean slate. First win is waiting.")
                self._sync_lesson(0, announce=True)
                self._refresh()

        # ── hints / fill ──

        def action_hint(self) -> None:
            self._show_hint()

        def action_fill_answer(self) -> None:
            if self.challenge and self.challenge["idx"] < len(self.challenge["items"]):
                les, m = self.challenge["items"][self.challenge["idx"]]
                self.query_one("#term_input", Input).value = m.accepted[0]
                self.query_one(CaptoPane).say("Filled — press Enter. Speed counts, no shame.")
                self.query_one("#term_input", Input).focus()
                return
            lesson = LESSONS[self.active_lesson]
            for m in lesson.missions:
                if tui_mission_key(lesson, m) not in self.shell.completed:
                    self.query_one("#term_input", Input).value = m.accepted[0]
                    self.query_one(CaptoPane).say(f"Filled “{m.accepted[0]}” — press Enter. 🎉")
                    self.query_one("#term_input", Input).focus()
                    return
            self.query_one(CaptoPane).say("All done here — pick the next lesson.")

        def _show_hint(self) -> None:
            if self.challenge and self.challenge["idx"] < len(self.challenge["items"]):
                les, m = self.challenge["items"][self.challenge["idx"]]
                self.query_one(CaptoPane).say(f"Challenge hint: {m.hint}")
                self.query_one(RichLog).write(f"[yellow]💛 Hint: {m.hint}[/]")
                return
            lesson = LESSONS[self.active_lesson]
            for m in lesson.missions:
                if tui_mission_key(lesson, m) not in self.shell.completed:
                    self.query_one(CaptoPane).say(f"Gentle nudge: {m.hint} (F2 fills it in.)")
                    self.query_one(RichLog).write(f"[yellow]💛 Hint: {m.hint} — F2 types it for you.[/]")
                    return
            self.query_one(CaptoPane).say("All done here — pick the next 👉 lesson.")

        # ── terminal ──

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw = event.value.strip()
            inp = self.query_one("#term_input", Input)
            inp.value = ""
            term = self.query_one(RichLog)
            capto = self.query_one(CaptoPane)
            if not raw:
                return
            if raw == "hint":
                self._show_hint()
                return
            # challenge consumes input first (still runs shell for FS realism when not skip)
            if self.challenge:
                if raw != "skip":
                    out = self.shell.run(raw)
                    if out and out not in ("__CLEAR__",) and not out.startswith("__EDITOR__:"):
                        for line in out.splitlines()[:10]:
                            term.write(f"  {line}")
                if self._challenge_answer(raw):
                    return
                # wrong challenge answer falls through to normal feedback below
            prompt = f"student:{self.shell.pwd()}$"
            term.write(f"[bold green]{prompt}[/] {raw}")
            out = self.shell.run(raw)
            if out == "__CLEAR__":
                term.clear()
                return
            if out.startswith("__EDITOR__:"):
                self._open_editor(out)
                return
            if out:
                for line in out.splitlines()[:40]:
                    term.write(f"  {line}")
            matched = self._check_missions(raw, term, capto)
            if matched:
                self._maybe_quiz(self.active_lesson)
            elif out and ("command not found" in out or "No such" in out or "missing" in out or "cannot" in out):
                term.write("[dim]Nothing broke — 'reset' rebuilds. Every pro typo'd this day one.[/]")
                capto.say(self._typo_hint(raw, out))
            elif not out:
                capto.say("Good — quiet means it worked. Try 'ls' to see what changed. 🌱")
            self._refresh()
            self.query_one(LessonDetail).show_lesson(self.active_lesson, self.shell)
            save_progress(self.shell, self.quiz_answered)

        def _open_editor(self, signal: str) -> None:
            parts = signal.split(":", 2)
            etype = parts[1] if len(parts) > 1 else "nano"
            fpath = parts[2] if len(parts) > 2 else ""
            if etype == "nano":
                self.push_screen(NanoScreen(self.shell, fpath), self._editor_done)
            else:
                self.push_screen(VimScreen(self.shell, fpath or "workshop.txt"), self._editor_done)

        def _editor_done(self, result: Optional[str]) -> None:
            if result:
                self.query_one(RichLog).write(f"[dim]{result}[/]")
                self.query_one(CaptoPane).say("Saved. 'cat <file>' to admire your work. ✨")
            self._refresh()
            self.query_one("#term_input", Input).focus()

        def _refresh(self) -> None:
            self.query_one(StatsBar).refresh_display(self.shell)
            self._sync_done_marks()
            save_progress(self.shell, self.quiz_answered)

        def _sync_done_marks(self) -> None:
            lv = self.query_one("#lesson_list", ListView)
            first_open = self._first_unfinished()
            for i, les in enumerate(LESSONS):
                done = all(tui_mission_key(les, m) in self.shell.completed for m in les.missions)
                try:
                    item = lv.children[i]
                    item.set_class(done, "-done")
                    item.set_class(i == first_open and not done, "-next")
                    prefix = "✓ " if done else ("👉 " if i == first_open else "   ")
                    item.query_one(Label).update(f"{prefix}{les.command:<10}")
                except Exception:
                    pass

        def _check_missions(self, raw: str, term: RichLog, capto: CaptoPane) -> bool:
            order = [self.active_lesson] + [i for i in range(len(LESSONS)) if i != self.active_lesson]
            for idx in order:
                lesson = LESSONS[idx]
                for m in lesson.missions:
                    key = tui_mission_key(lesson, m)
                    if key in self.shell.completed:
                        continue
                    if tui_command_matches(raw, m.accepted):
                        self.shell.completed.add(key)
                        self.shell.accomplished_commands.append(_tui_normalize(raw))
                        new_lvl = self.shell.add_xp(m.xp)
                        self.shell.score += m.xp
                        term.write(f"[bold green]🎉 Nice! +{m.xp} XP.[/]  {m.explanation}")
                        capto.say(f"{random.choice(AFFIRMATIONS)} Next tiny win awaits. 👉")
                        if new_lvl:
                            term.write(f"[bold yellow]★ Leveled up → {new_lvl} {tui_level_badge(new_lvl)}[/]")
                        if idx != self.active_lesson:
                            term.write(f"[dim](credited to {lesson.command})[/]")
                        # after mission, advance lesson if active one finished
                        nxt = self._next_lesson(LESSONS[self.active_lesson])
                        if nxt and all(tui_mission_key(LESSONS[self.active_lesson], mm) in self.shell.completed for mm in LESSONS[self.active_lesson].missions):
                            term.write(f"[cyan]── Up next: {nxt.command} — {nxt.title} (F3 for the full card) ──[/]")
                        return True
            return False

        def _lesson_success(self, lesson, raw: str, out: str) -> bool:
            raw = raw.strip()
            if not raw:
                return False
            try:
                cmd = shlex.split(raw)[0]
            except ValueError:
                return False
            accepted = lesson.command.split("/")
            if "|" in lesson.command or "|" in raw:
                accepted.append("pipe")
            bad = ["command not found", "No such", "missing", "cannot", "not a directory", "syntax error"]
            if cmd not in accepted and not ("|" in raw and lesson.command == "pipe (|)"):
                return False
            return not any(m in out for m in bad)

        def _maybe_quiz(self, lesson_idx: int) -> None:
            lesson = LESSONS[lesson_idx]
            # quiz triggers when the typed command ran clean for that lesson
            # caller already ran shell; re-evaluate last command
            last = self.shell.command_log[-1] if self.shell.command_log else ""
            out_markers_ok = True  # mission already matched => output was clean enough
            if self._lesson_success(lesson, last, "") or out_markers_ok:
                if lesson.command in QUIZ_QUESTIONS:
                    self.push_screen(QuizScreen(lesson_idx), lambda ans: self._quiz_done(lesson_idx, ans))

        def _quiz_done(self, lesson_idx: int, answer: Optional[str]) -> None:
            lesson = LESSONS[lesson_idx]
            term = self.query_one(RichLog)
            if answer is None or not answer.strip():
                term.write("[dim]Quiz skipped — the mission XP is still yours.[/]")
                self.query_one("#term_input", Input).focus()
                return
            quiz = QUIZ_QUESTIONS[lesson.command]
            if any(k in answer.strip().lower() for k in quiz["keys"]):
                if lesson.command in self.quiz_answered:
                    term.write("[green]✓ Correct — review complete.[/]")
                else:
                    self.quiz_answered.add(lesson.command)
                    new_lvl = self.shell.add_xp(15)
                    self.shell.score += 5
                    self.shell.accomplished_commands.append(f"concept:{lesson.command}")
                    term.write("[green]✓ Correct. +15 XP concept bonus.[/]")
                    if new_lvl:
                        term.write(f"[bold yellow]★ Level {new_lvl}[/]")
                self.query_one(CaptoPane).say(random.choice(AFFIRMATIONS))
            else:
                term.write("[red]Not quite — re-read F3, try F7 examples. No XP lost.[/]")
                self.query_one(CaptoPane).say("Good attempt — peep F3, then I'll re-quiz next win. 💛")
            self._refresh()
            self.query_one("#term_input", Input).focus()

        def _next_lesson(self, lesson):
            for i, les in enumerate(LESSONS):
                if les.command == lesson.command and i + 1 < len(LESSONS):
                    return LESSONS[i + 1]
            return None

        def _typo_hint(self, raw: str, out: str) -> str:
            try:
                cmd = shlex.split(raw)[0]
            except Exception:
                return "Hmm, try one word like 'pwd'. Nothing broke. 💛"
            known = [les.command for les in LESSONS] + ["help", "clear", "history"]
            common = {"sl": "ls", "l": "ls", "ll": "ls -la", "cd..": "cd ..", "pdw": "pwd", "pw": "pwd",
                      "mkkdir": "mkdir", "touh": "touch", "cta": "cat", "ceho": "echo", "gerp": "grep"}
            if cmd in common:
                return f"Close! Did you mean '{common[cmd]}'? 🌱 ({out})"
            import difflib
            close = difflib.get_close_matches(cmd, known, n=1, cutoff=0.5)
            if close and close[0] != cmd:
                return f"Close! Did you mean '{close[0]}'? 🌱 ({out})"
            lesson = LESSONS[self.active_lesson]
            if lesson.missions:
                return f"Good try — for this goal try: {lesson.missions[0].accepted[0]} (F1/F2)."
            return f"Good try — {out}"

        def on_unmount(self) -> None:
            try:
                save_progress(self.shell, self.quiz_answered)
            except Exception:
                pass


    class ResetScreen(ModalScreen):
        CSS = """
        ResetScreen { align: center middle; }
        #reset_box { border: round #ff5555; background: #1c0f14; padding: 1 3; width: 52; height: auto; }
        #reset_title { text-style: bold; color: #ff5555; height: 1; }
        #reset_btns { height: 3; margin-top: 1; }
        """

        def compose(self) -> ComposeResult:
            with Vertical(id="reset_box"):
                yield Label("Reset playground + progress?", id="reset_title")
                yield Label("Clears XP, goals, and fake files. Nothing real is touched.", id="reset_body")
                with Horizontal(id="reset_btns"):
                    yield Button("Yes, fresh start", id="yes", variant="error")
                    yield Button("Cancel", id="no", variant="primary")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(event.button.id)

else:
    # textual missing: stubs so `from linuxx import LNXXApp` never crashes
    # engine and --test. TUI launch will attempt auto-install.
    StatsBar = LessonDetail = CaptoPane = WelcomeScreen = QuizScreen = None  # type: ignore
    NanoScreen = VimScreen = ResetScreen = None  # type: ignore
    LNXXApp = None  # type: ignore


# ─────────────────────────── Tests ───────────────────────────

class LinuxxTests(unittest.TestCase):
    def test_core_shell_behaviors(self):
        shell = FakeShell()

        self.assertEqual(shell.run("pwd"), "/home/student")
        self.assertIn("readme.txt", shell.run("ls"))
        self.assertNotIn(".bashrc", shell.run("ls"))
        self.assertIn(".bashrc", shell.run("ls -a"))
        self.assertIn(".bashrc", shell.run("ls -la"))

        self.assertEqual(shell.run("cd Documents"), "")
        self.assertEqual(shell.pwd(), "/home/student/Documents")
        self.assertEqual(shell.run("cd .."), "")
        self.assertEqual(shell.pwd(), "/home/student")

        self.assertEqual(shell.run("mkdir practice"), "")
        self.assertIn("practice", shell.run("ls"))

        self.assertEqual(shell.run("mkdir -p deep/nested/path"), "")
        self.assertEqual(shell.run("cd deep"), "")
        self.assertEqual(shell.run("cd .."), "")

        self.assertEqual(shell.run("touch todo.txt"), "")
        self.assertIn("todo.txt", shell.run("ls"))

        self.assertIn("Welcome to Linux Command Trainer", shell.run("cat readme.txt"))
        self.assertIn("1  ", shell.run("cat -n notes.txt"))

        self.assertEqual(shell.run("echo hello"), "hello")
        self.assertIn("/home/student", shell.run("echo $HOME"))

        self.assertEqual(shell.run("cp readme.txt readme_backup.txt"), "")
        self.assertIn("readme_backup.txt", shell.run("ls"))
        self.assertEqual(shell.run("cp readme.txt Documents"), "")
        self.assertEqual(shell._get_abs(shell._resolve("Documents")).type, "dir")
        self.assertIn("readme.txt", shell.run("ls Documents"))

        self.assertEqual(shell.run("mv old.txt new.txt"), "")
        self.assertIn("new.txt", shell.run("ls"))
        self.assertNotIn("old.txt", shell.run("ls"))
        self.assertIn("subdirectory of itself", shell.run("mv projects projects/linux/foo"))
        self.assertIsNotNone(shell._get_abs(shell._resolve("projects")))

        self.assertEqual(shell.run("rm temp.txt"), "")
        self.assertNotIn("temp.txt", shell.run("ls"))
        self.assertIn("Is a directory", shell.run("rm -f Documents"))
        self.assertEqual(shell._get_abs(shell._resolve("Documents")).type, "dir")
        self.assertEqual(shell.run("rm -f missing.txt"), "")

        self.assertIn("linux commands are composable", shell.run("grep linux notes.txt"))
        self.assertIn("ERROR", shell.run("grep -i error log.txt"))

        self.assertTrue(shell.run("wc -l log.txt").strip().startswith("6"))
        self.assertIn("INFO  retry successful", shell.run("tail log.txt"))
        self.assertIn("INFO  boot ok", shell.run("head -n 1 log.txt"))

        self.assertEqual(shell.run("chmod +x script.sh"), "")
        self.assertIn("-rwxr-xr-x", shell.run("ls -l"))
        self.assertIn("PID", shell.run("ps"))
        self.assertIn("terminated", shell.run("kill 404"))

    def test_pipe_and_redirect_regressions(self):
        shell = FakeShell()

        self.assertTrue(shell.run("ls | wc -l").strip().isdigit())
        self.assertIn("ERROR", shell.run("cat log.txt | grep ERROR"))

        self.assertEqual(shell.run('echo "a > b"'), "a > b")
        self.assertEqual(shell.run("echo hi > out.txt"), "")
        self.assertEqual(shell.run("cat out.txt"), "hi")
        self.assertEqual(shell.run("echo there >> out.txt"), "")
        self.assertEqual(shell.run("cat out.txt"), "hi\nthere")
        self.assertEqual(shell.run("cat > empty.txt"), "")
        self.assertEqual(shell.run("cat empty.txt"), "")
        self.assertIn("Is a directory", shell.run("echo nope > Documents"))
        self.assertEqual(shell._get_abs(shell._resolve("Documents")).type, "dir")

    def test_history_and_repeat_last_command(self):
        shell = FakeShell()

        self.assertIn("event not found", shell.run("!!"))
        self.assertEqual(shell.run("pwd"), "/home/student")
        self.assertEqual(shell.run("!!"), "/home/student")
        history = shell.run("history")
        self.assertIn("pwd", history)
        self.assertIn("history", history)
        self.assertIn("history", shell.run("history 1"))
        self.assertIn("pwd", shell.run("history | grep pwd"))

    def test_progress_persists_fake_filesystem(self):
        global SAVE_FILE
        old_save_file = SAVE_FILE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                SAVE_FILE = os.path.join(tmp, "progress.json")
                shell = FakeShell()
                shell.run("mkdir practice")
                shell.run("echo saved > practice/file.txt")
                shell.run("cd practice")
                shell.xp = 75
                shell.score = 25
                shell.completed.add("demo:mission")

                save_progress(shell, {"pwd"})

                loaded = FakeShell()
                quiz_answered: set = set()
                load_progress(loaded, quiz_answered)

                self.assertEqual(loaded.pwd(), "/home/student/practice")
                self.assertEqual(loaded.run("cat file.txt"), "saved")
                self.assertEqual(loaded.xp, 75)
                self.assertEqual(loaded.score, 25)
                self.assertIn("demo:mission", loaded.completed)
                self.assertIn("pwd", quiz_answered)
        finally:
            SAVE_FILE = old_save_file

    def test_mission_command_matching_accepts_equivalent_forms(self):
        self.assertTrue(engine_command_matches("ls -al", ["ls -la"]))
        self.assertTrue(engine_command_matches("mkdir projects/linux -p", ["mkdir -p projects/linux"]))
        self.assertTrue(engine_command_matches('find . -name "*.txt"', ["find . -name '*.txt'"]))
        self.assertTrue(engine_command_matches("ls|wc -l", ["ls | wc -l"]))
        self.assertTrue(engine_command_matches('grep -i "error" log.txt', ["grep -i error log.txt"]))
        self.assertFalse(engine_command_matches("rm other.txt", ["rm temp.txt"]))
        # TUI wrapper uses the same engine
        self.assertTrue(tui_command_matches("ls -al", ["ls -la"]))
        self.assertTrue(command_matches("ls|wc -l", ["ls | wc -l"]))

    def test_engine_helpers_and_content(self):
        shell2 = FakeShell()
        self.assertEqual(shell2.level(), 1)
        shell2.xp = 50
        self.assertEqual(shell2.level(), 2)

        shell2.run("touch keep.txt")
        self.assertIn("keep.txt", shell2.run("ls"))
        self.assertGreaterEqual(len(AFFIRMATIONS), 5)
        self.assertGreaterEqual(len(TIPS_OF_THE_DAY), 5)
        self.assertEqual(LESSONS[0].command, "pwd")
        self.assertEqual(LESSONS[1].command, "ls")
        self.assertEqual(engine_mission_key(LESSONS[0], LESSONS[0].missions[0]),
                         f"pwd:{LESSONS[0].missions[0].prompt}")
        self.assertEqual(len(VIM_STEPS), 12)

    def test_vim_editor_modes_used_by_tui(self):
        shell = FakeShell()
        vim = VimEditor(shell, "workshop.txt")
        self.assertEqual(vim.mode, "normal")
        vim._handle("i")
        self.assertEqual(vim.mode, "insert")
        vim._handle("ESC")
        self.assertEqual(vim.mode, "normal")

    def test_tui_available(self):
        # TUI is the default entry point; it must exist when textual is installed.
        self.assertIsNotNone(LNXXApp)


def run_tests() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LinuxxTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("All tests passed.")


# ─────────────────────────── Entry point ───────────────────────────
# TUI is the default. Classic CLI was removed.

def _launch_tui_or_install() -> None:
    if LNXXApp is None:
        print("  TUI needs the 'textual' package — attempting auto-install…")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "textual"])
        except Exception as e:
            print(f"  Auto-install failed: {e}")
            print("  Install manually:  pip install textual")
            print("  Then run:  python linuxx.py")
            sys.exit(1)
        print("  Installed. Re-launching…")
        try:
            os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
        except Exception:
            print("  Installed textual — please re-run:  python linuxx.py")
            sys.exit(1)
    try:
        LNXXApp().run()
    except KeyboardInterrupt:
        print("\n  Interrupted. Progress auto-saved on clean exits.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_tests()
    elif len(sys.argv) > 1 and sys.argv[1] == "--classic":
        print("  Classic CLI was removed. The TUI is now the default:  python linuxx.py")
        sys.exit(2)
    else:
        # Default (no args) and --tui alias both launch the TUI.
        _launch_tui_or_install()
