import cv2
import os
import time
import subprocess
import sys
import numpy as np

# Сбалансированный набор символов (от самого плотного к самому легкому)
ASCII_CHARS = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

def play_high_res_color_video(video_path, target_width=150):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Ошибка: Не удалось открыть видеофайл {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_delay = 1.0 / fps if fps > 0 else 1.0 / 30.0

    orig_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    orig_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    aspect_ratio = orig_height / orig_width if orig_width else 1.0
    
    # Коррекция вертикального шага шрифта терминала
    target_height = max(1, int(target_width * aspect_ratio * 0.48))

    ascii_bytes = ASCII_CHARS.encode('ascii')
    num_chars = len(ASCII_CHARS)

    os.system('clear')
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    # Запуск звука с корректным строковым путем к видео
    audio_process = None
    try:
        audio_process = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(video_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"Предупреждение: Не удалось запустить звук ({e})")
        audio_process = None

    start_time = time.time()
    frame_count = 0

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            resized_frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

            b = resized_frame[:, :, 0]
            g = resized_frame[:, :, 1]
            r = resized_frame[:, :, 2]

            # Вычисление яркости
            gray = ((r.astype(np.uint32) * 77 + g.astype(np.uint32) * 150 + b.astype(np.uint32) * 29) >> 8).astype(np.uint8)
            
            # ИСПРАВЛЕНО: Равномерное и точное распределение яркости по индексам через numpy
            min_val, max_val = gray.min(), gray.max()
            if max_val > min_val:
                # Нормализуем строго в диапазон индексов символов (от 0 до num_chars - 1)
                char_indices = ((gray.astype(np.float32) - min_val) / (max_val - min_val) * (num_chars - 1)).astype(np.uint8)
            else:
                char_indices = np.zeros_like(gray, dtype=np.uint8)

            buffer = bytearray()
            buffer.extend(b"\033[H") # Сброс курсора в начало экрана

            last_r, last_g, last_b = -1, -1, -1

            for y in range(target_height):
                row_r = r[y]
                row_g = g[y]
                row_b = b[y]
                row_chars = char_indices[y]

                for x in range(target_width):
                    pr, pg, pb = row_r[x], row_g[x], row_b[x]
                    
                    # Переключаем ANSI-цвет только при необходимости
                    if pr != last_r or pg != last_g or pb != last_b:
                        buffer.extend(f"\033[38;2;{pr};{pg};{pb}m".encode('ascii'))
                        last_r, last_g, last_b = pr, pg, pb
                    
                    # Извлекаем правильный разнообразный символ из массива
                    buffer.append(ascii_bytes[row_chars[x]])
                
                buffer.extend(b"\n")

            sys.stdout.buffer.write(buffer)
            sys.stdout.buffer.flush()

            frame_count += 1

            # Потоковая синхронизация кадров
            expected_time = start_time + (frame_count * frame_delay)
            current_time = time.time()
            sleep_time = expected_time - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.05:
                cap.grab()
                frame_count += 1

    except KeyboardInterrupt:
        print("\nВоспроизведение остановлено.")
    finally:
        cap.release()
        if audio_process is not None:
            audio_process.terminate()
        print("\033[0m\nГотово!")

if __name__ == "__main__":
    # ИСПРАВЛЕНО: Теперь корректно берется элемент sys.argv[1], если передан аргумент
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
    else:
        video_file = "video.mp4"
    
    play_high_res_color_video(video_file, target_width=250)
