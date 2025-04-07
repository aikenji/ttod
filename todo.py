#!/usr/bin/env python3
import curses
import json
import os
from curses import wrapper
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class TodoItem:
    def __init__(self, text: str, done: bool = False, deadline: Optional[str] = None):
        self.text = text
        self.done = done
        self.deadline = deadline if deadline else None

    def to_dict(self) -> Dict:
        return {"text": self.text, "done": self.done, "deadline": self.deadline}

    @classmethod
    def from_dict(cls, data: Dict) -> "TodoItem":
        return cls(data["text"], data["done"], data.get("deadline"))


class TodoList:
    def __init__(self):
        self.todos: List[TodoItem] = []
        self.cursor_pos = 0
        self.filename = os.path.expanduser("~/.vim_todo.json")
        self.load()

    def add(self, text: str, deadline: Optional[str] = None):
        self.todos.append(TodoItem(text, False, deadline))
        self.save()

    def toggle(self, index: int):
        if 0 <= index < len(self.todos):
            self.todos[index].done = not self.todos[index].done
            self.save()

    def delete(self, index: int):
        if 0 <= index < len(self.todos):
            del self.todos[index]
            if self.cursor_pos >= len(self.todos):
                self.cursor_pos = max(0, len(self.todos) - 1)
            self.save()

    def edit(self, index: int, new_text: str, new_deadline: Optional[str] = None):
        if 0 <= index < len(self.todos):
            self.todos[index].text = new_text
            self.todos[index].deadline = new_deadline
            self.save()

    def move_up(self):
        if self.cursor_pos > 0:
            self.cursor_pos -= 1

    def move_down(self):
        if self.cursor_pos < len(self.todos) - 1:
            self.cursor_pos += 1

    def save(self):
        with open(self.filename, "w") as f:
            json.dump([todo.to_dict() for todo in self.todos], f)

    def load(self):
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
                self.todos = [TodoItem.from_dict(item) for item in data]
        except (FileNotFoundError, json.JSONDecodeError):
            self.todos = []


def parse_deadline(deadline_str: str) -> Optional[datetime]:
    if not deadline_str:
        return None

    try:
        # Try to parse as YYYY-MM-DD
        return datetime.strptime(deadline_str, "%Y-%m-%d")
    except ValueError:
        pass

    try:
        # Try to parse as MM-DD
        now = datetime.now()
        deadline = datetime.strptime(deadline_str, "%m-%d")
        return deadline.replace(year=now.year)
    except ValueError:
        pass

    try:
        # Try to parse as "in X days"
        if deadline_str.startswith("in "):
            days = int(deadline_str[3:].split()[0])
            return datetime.now() + timedelta(days=days)
    except (ValueError, IndexError):
        pass

    return None


def get_deadline_color(deadline_str: str) -> int:
    deadline = parse_deadline(deadline_str)
    if not deadline:
        return curses.COLOR_WHITE

    now = datetime.now()
    delta = deadline - now

    if delta.days < 0:
        # Overdue
        return curses.COLOR_RED
    elif delta.days <= 2:
        # Due in 1-2 days
        return curses.COLOR_YELLOW
    elif delta.days <= 7:
        # Due in 3-7 days
        return curses.COLOR_CYAN
    else:
        # Due in more than a week
        return curses.COLOR_GREEN


def init_colors():
    curses.start_color()
    curses.use_default_colors()  # same color as terminal
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # Normal
    curses.init_pair(2, curses.COLOR_RED, -1)  # Overdue
    curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Urgent
    curses.init_pair(4, curses.COLOR_MAGENTA, -1)
    curses.init_pair(5, curses.COLOR_CYAN, -1)  # Soon
    curses.init_pair(6, curses.COLOR_WHITE, -1)  # Done
    curses.init_pair(7, curses.COLOR_BLUE, -1)  # Help text
    MY_WHITE = 10
    curses.init_color(MY_WHITE, 900, 900, 900)
    curses.init_pair(10, MY_WHITE, -1)


def sort_todos_by_days(todo_list: TodoList) -> List[Tuple[TodoItem, int]]:
    """sorting by due days（completed at bottom）"""
    now = datetime.now()
    sorted_todos = []

    for idx, todo in enumerate(todo_list.todos):
        if not todo.deadline:
            days = float("inf")
            priority = 1
        else:
            deadline = parse_deadline(todo.deadline)
            if deadline:
                days = (deadline - now).days
                priority = 2 if not todo.done else 0
            else:
                days = float("inf")
                priority = 1

        sorted_todos.append((priority, days, todo, idx))

    # 新的排序规则：
    # 1. 首先按优先级排序（2 > 1 > 0）
    # 2. 然后按天数排序（正序，天数少的排前面）
    sorted_todos.sort(key=lambda x: (-x[0], x[1]))
    # return (sorted_todos, original_index)
    return [(item[2], item[3]) for item in sorted_todos]


def draw_todo_list(
    stdscr, todo_list: TodoList, days_mode: bool = False, sorted_by_days: bool = False
):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    # Title
    title = "Todo List by Dr.G ver 1.0"
    separator = "=" * width

    stdscr.addstr(
        0, (width - len(title)) // 2, title, curses.color_pair(7) | curses.A_BOLD
    )
    stdscr.addstr(1, 0, separator, curses.color_pair(7))

    # get todo list items
    display_todos = (
        [item[0] for item in sort_todos_by_days(todo_list)]
        if sorted_by_days
        else todo_list.todos
    )

    # Todo items
    for i, todo in enumerate(display_todos):
        y = i + 3
        if y >= height - 2:
            break

        # Cursor
        cursor = ">" if i == todo_list.cursor_pos else " "
        stdscr.addstr(y, 0, cursor)

        # Checkbox
        checkbox = "[x]" if todo.done else "[ ]"
        if todo.done:
            checkbox_attr = curses.color_pair(1)
        else:
            checkbox_attr = curses.color_pair(10)
        stdscr.addstr(y, 2, checkbox, checkbox_attr)

        # Text
        text = todo.text
        if todo.done:
            text_attr = curses.color_pair(6) | curses.A_DIM
        else:
            text_attr = curses.color_pair(4)

        stdscr.addstr(y, 6, text, text_attr)

        # Deadline
        deadline_text = ""
        if todo.deadline:
            deadline = parse_deadline(todo.deadline)
            if deadline:
                if days_mode:
                    days = (deadline - datetime.now()).days
                    if days < 0:
                        deadline_text = f"(overdue {-days}d)"
                    else:
                        deadline_text = f"(in {days}d)"
                else:
                    deadline_text = f"({todo.deadline})"

        if todo.deadline:
            deadline_color = get_deadline_color(todo.deadline)
            color_pair = None

            if deadline_color == curses.COLOR_RED:
                color_pair = 2
            elif deadline_color == curses.COLOR_YELLOW:
                color_pair = 3
            elif deadline_color == curses.COLOR_CYAN:
                color_pair = 5
            else:
                color_pair = 1

            deadline_attr = curses.color_pair(color_pair)
            if todo.done:
                deadline_attr = curses.color_pair(6) | curses.A_DIM

            # Position deadline at the end of the line
            deadline_pos = width - len(deadline_text) - 1
            stdscr.addstr(y, deadline_pos, deadline_text, deadline_attr)

    # Status line
    status_line = f"{len([t for t in todo_list.todos if t.done])}/{len(todo_list.todos)} completed "
    if days_mode:
        status_line += " [D]"
    else:
        status_line += " [ ]"
    if sorted_by_days:
        status_line += "[S]"
    else:
        status_line += "[ ]"
    stdscr.addstr(height - 1, 0, status_line, curses.color_pair(7))

    stdscr.refresh()


def show_help(stdscr):
    height, width = stdscr.getmaxyx()

    help_text = [
        "Vim Todo List Help",
        "",
        "Navigation:",
        "  j/k - Move cursor down/up",
        "",
        "Actions:",
        "  a - Add new todo",
        "  e - Edit current todo",
        "  d - Delete current todo",
        "  x - Toggle completion status",
        "  t - Toggle days mode",
        "  s - Toggle sorting mode",
        "  :w - Save todos",
        "  :q - Quit",
        "",
        "Press any key to return",
    ]

    # Create a centered window for help
    help_height = len(help_text) + 4
    help_width = max(len(line) for line in help_text) + 4
    win_y = (height - help_height) // 2
    win_x = (width - help_width) // 2

    help_win = curses.newwin(help_height, help_width, win_y, win_x)
    help_win.border()

    for i, line in enumerate(help_text):
        help_win.addstr(i + 2, 2, line, curses.color_pair(7))

    help_win.refresh()
    help_win.getch()


def edit_popup(stdscr, title: str, initial_text: str) -> str:
    height, width = stdscr.getmaxyx()
    popup_h = 3
    popup_w = min(60, width - 4)

    y = (height - popup_h) // 2
    x = (width - popup_w) // 2

    popup = curses.newwin(popup_h, popup_w, y, x)
    popup.keypad(True)  # enable special keys
    popup.attron(curses.color_pair(3))
    popup.border()
    popup.border()
    popup.addstr(0, 2, f" {title} ")

    text = initial_text
    pos = len(text)
    popup.addstr(1, 1, text)

    curses.curs_set(1)

    while True:
        popup.move(1, 1)
        popup.clrtoeol()
        popup.addstr(1, 1, text)
        popup.move(1, pos + 1)

        ch = popup.getch()

        if ch == 10:  # Enter
            break
        elif ch == 27:  # ESC
            text = initial_text
            break
        elif ch == curses.KEY_BACKSPACE or ch == 127:
            if pos > 0:
                text = text[: pos - 1] + text[pos:]
                pos -= 1
        elif ch == curses.KEY_LEFT:
            pos = max(0, pos - 1)
        elif ch == curses.KEY_RIGHT:
            pos = min(len(text), pos + 1)
        elif 32 <= ch <= 126:  # legal char
            text = text[:pos] + chr(ch) + text[pos:]
            pos += 1

    curses.curs_set(0)
    return text


def main(stdscr):
    curses.curs_set(0)  # display cursor
    init_colors()
    days_mode = False
    sorted_by_days = False

    todo_list = TodoList()

    while True:
        draw_todo_list(stdscr, todo_list, days_mode, sorted_by_days)
        idx = (
            [item[1] for item in sort_todos_by_days(todo_list)]
            if sorted_by_days
            else range(len(todo_list.todos))
        )
        key = stdscr.getch()

        if key == ord("j"):
            todo_list.move_down()
        elif key == ord("k"):
            todo_list.move_up()
        elif key == ord("x"):
            todo_list.toggle(idx[todo_list.cursor_pos])
        elif key == ord("d"):
            en = edit_popup(stdscr, "Input y to delete", "")
            if en == "y":
                todo_list.delete(idx[todo_list.cursor_pos])
        elif key == ord("a"):
            text = edit_popup(stdscr, "Add todo: ", "")
            if text:
                deadline = edit_popup(
                    stdscr, "Deadline (YYYY-MM-DD, MM-DD, or 'in X days'): ", ""
                )
                todo_list.add(text, deadline if deadline else None)
        elif key == ord("e"):
            if todo_list.todos:
                current = todo_list.todos[idx[todo_list.cursor_pos]]
                # edit text in popup
                new_text = edit_popup(stdscr, "Edit Todo", current.text)

                # edit deadline in popup
                current_deadline = current.deadline if current.deadline else ""
                new_deadline = edit_popup(stdscr, "Edit Deadline", current_deadline)

                if new_text != current.text or new_deadline != current_deadline:
                    todo_list.edit(
                        idx[todo_list.cursor_pos],
                        new_text,
                        new_deadline if new_deadline else None,
                    )

        elif key == ord(":"):
            cmd = edit_popup(stdscr, "Command", "")
            if cmd == "w":
                todo_list.save()
            elif cmd == "q":
                break
        elif key == ord("h"):
            show_help(stdscr)
        elif key == ord("t"):
            days_mode = not days_mode
        elif key == ord("s"):
            sorted_by_days = not sorted_by_days
        elif key == 27:  # ESC key
            pass


if __name__ == "__main__":
    wrapper(main)
