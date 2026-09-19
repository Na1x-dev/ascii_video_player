import cv2
import os
import sys
import numpy as np
import base64
import zlib
import subprocess

ASCII_CHARS = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

def compile_video_to_script(video_path, output_script="player_video.py", target_width=150):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Ошибка: Не удалось открыть видео {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    orig_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    orig_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    aspect_ratio = orig_height / orig_width if orig_width else 1.0
    
    # Автоматический расчет высоты с учетом пропорций и вытянутости шрифта
    target_height = max(1, int(target_width * aspect_ratio * 0.48))

    ascii_bytes = ASCII_CHARS.encode('ascii')
    num_chars = len(ASCII_CHARS)

    print(f"[*] Целевая ширина: {target_width} символов (Высота рассчитана: {target_height})")
    print(f"[*] Кадров в секунду (FPS): {fps}")
    print(f"[*] Конвертация кадров в ASCII-байты. Пожалуйста, подождите...")

    all_frames_data = bytearray()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
        b, g, r = resized[:, :, 0], resized[:, :, 1], resized[:, :, 2]

        gray = ((r.astype(np.uint32) * 77 + g.astype(np.uint32) * 150 + b.astype(np.uint32) * 29) >> 8).astype(np.uint8)
        min_val, max_val = gray.min(), gray.max()
        if max_val > min_val:
            char_indices = ((gray.astype(np.float32) - min_val) / (max_val - min_val) * (num_chars - 1)).astype(np.uint8)
        else:
            char_indices = np.zeros_like(gray, dtype=np.uint8)

        frame_buf = bytearray()
        last_r, last_g, last_b = -1, -1, -1

        for y in range(target_height):
            row_r, row_g, row_b, row_chars = r[y], g[y], b[y], char_indices[y]
            for x in range(target_width):
                pr, pg, pb = row_r[x], row_g[x], row_b[x]
                if pr != last_r or pg != last_g or pb != last_b:
                    frame_buf.extend(f"\033[38;2;{pr};{pg};{pb}m".encode('ascii'))
                    last_r, last_g, last_b = pr, pg, pb
                frame_buf.append(ascii_bytes[row_chars[x]])
            frame_buf.extend(b"\n")

        all_frames_data.extend(frame_buf + b"===FRAME_END===")

    cap.release()

    # Сжимаем данные
    compressed_frames = zlib.compress(all_frames_data, level=9)
    encoded_frames = base64.b64encode(compressed_frames).decode('ascii')

    print("[*] Извлечение аудиодорожки...")
    temp_audio = "temp_compile_audio.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "libmp3lame", "-loglevel", "quiet", temp_audio],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    encoded_audio = ""
    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
        with open(temp_audio, "rb") as f:
            encoded_audio = base64.b64encode(f.read()).decode('ascii')
        os.remove(temp_audio)
    else:
        print("[!] Аудиодорожка не найдена или не извлечена.")

    # Шаблон генерируемого плеера
    template = f'''# Автоматически сгенерированный плеер ASCII-видео
import time
import sys
import os
import base64
import zlib
import subprocess
import shutil

COMPRESSED_FRAMES = "{encoded_frames}"
AUDIO_DATA = "{encoded_audio}"
FPS = {fps}

def is_termux():
    return "com.termux" in os.environ.get("PREFIX", "")

def play():
    raw_data = zlib.decompress(base64.b64decode(COMPRESSED_FRAMES))
    frames = raw_data.split(b"===FRAME_END===")[:-1]
    
    temp_audio_path = "runtime_audio.mp3"
    audio_process = None
    termux_env = is_termux()
    
    if AUDIO_DATA:
        try:
            with open(temp_audio_path, "wb") as f:
                f.write(base64.b64decode(AUDIO_DATA))
            
            if termux_env and shutil.which("termux-play-audio"):
                audio_process = subprocess.Popen(["termux-play-audio", temp_audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("ffplay"):
                audio_process = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    os.system('clear')
    sys.stdout.write("\\033[2J\\033[H")
    sys.stdout.flush()

    frame_delay = 1.0 / FPS
    start_time = time.time()
    
    try:
        for idx, frame in enumerate(frames):
            sys.stdout.buffer.write(b"\\033[H" + frame)
            sys.stdout.buffer.flush()
            
            expected_time = start_time + (idx * frame_delay)
            sleep_time = expected_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        pass
    finally:
        if audio_process:
            if termux_env:
                subprocess.run(["termux-play-audio", "--stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                audio_process.terminate()
        if os.path.exists(temp_audio_path):
            try: os.remove(temp_audio_path)
            except: pass
        print("\\033[0m\\nГотово!")

if __name__ == "__main__":
    play()
'''

    with open(output_script, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"[+] Скрипт успешно скомпилирован в: {output_script}")

if __name__ == "__main__":
    # ИСПРАВЛЕНО: Гибкий разбор аргументов командной строки
    video_file = "video.mp4"
    width = 150

    # Если передан хотя бы один аргумент (путь к файлу)
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
    
    # Если передан второй аргумент (ширина)
    if len(sys.argv) > 2:
        try:
            width = int(sys.argv[2])
        except ValueError:
            print(f"[!] Ошибка: Указанная ширина '{sys.argv[2]}' не является числом. Ипользуется значение 150.")

    compile_video_to_script(video_file, target_width=width)
