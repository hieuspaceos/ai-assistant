#!/usr/bin/env python3
"""tts-vieneu.py — sinh giọng nói tiếng Việt bằng VieNeu-TTS (v3 Turbo, local).

Dùng:  python3 tools/tts-vieneu.py "câu cần đọc" out.wav [voice]
Cần:   venv đã `pip install vieneu` (chạy bằng python của venv đó).
Giọng: truyền tên preset ở tham số 3, mặc định lấy TTS_VOICE env hoặc "Trúc Ly".
Danh sách giọng: python3 tools/tts-vieneu.py --voices
"""
import os
import sys


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--voices':
        from vieneu import Vieneu
        for label, vid in Vieneu().list_preset_voices():
            print(f'{label} | {vid}')
        return

    if len(sys.argv) < 3:
        sys.exit(__doc__)

    text, out_wav = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('TTS_VOICE', 'Trúc Ly')

    from vieneu import Vieneu
    t = Vieneu()
    audio = t.infer(text, voice=voice)
    t.save(audio, out_wav)


if __name__ == '__main__':
    main()
