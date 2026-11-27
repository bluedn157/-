"""Flash arithmetic build settings for the Yeongaesomun v1.1.6 map."""
from typing import Dict
import inspect
import codecs
import re
import csv
import io
import os
import unicodedata
from eudplib import *
from main import settings


ESCAPE_SEQUENCE_RE = re.compile(r"(\\x..)|(\\n)")


def decode_match(match):
    return codecs.decode(match.group(0), "unicode-escape")


def escape_hex_newline(value):
    return ESCAPE_SEQUENCE_RE.sub(decode_match, value)


def init():
    # EUDDraft injects chatEvent through its plugin configuration.
    for frame_info in inspect.stack():
        if frame_info.function == 'loadPluginsFromConfig':
            chat_event_settings: Dict[str, str] = frame_info.frame.f_locals['config']['chatEvent']
            break
    else:
        raise RuntimeError("build_settings.py must be loaded by EUDDraft")

    # Restore the original map sound files configured in build.eds.
    for effect_file_name in (
        'opening_sound_1', 'opening_sound_2', 'click_sound',
        'skip_sound', 'correct_sound', 'buzzer'
    ):
        if effect_file_name not in settings:
            continue
        with open(f"effect/{settings[effect_file_name]}", 'rb') as f:
            MPQAddFile(effect_file_name, f.read())


# Legacy exports retained for the original opening and MusicSetting modules.
leaderboard_text = escape_hex_newline(settings["leaderboard_text"])
AnswerKey = EUDArray([EUDArray([0])])
MusicHint1 = EUDArray([0])
MusicHint2 = EUDArray([0])
MusicLength = EUDArray([1])
MusicAnswer = EUDArray([0])
MusicNumber = 1
MusicStart = 0
MusicEnd = 0
VoteNum = EUDArray([1, 2, 2, 3, 3, 4, 4])
EndingMusic = 1
SegmentCount = EUDArray([0, 0])
CategoryCount = 0
CategoryNames = EUDArray([0])
CategoryDescriptions = EUDArray([0])
CategoryMusics = EUDArray([EUDArray([0])])
MinQuestionLength = 1
settingName3 = Db("힌트1")
settingName4 = Db("힌트2")


# ===========================================================================
# 문제 데이터: Map/questions.csv 를 빌드할 때 읽어서 게임에서 쓰는 배열로 만듭니다.
# 문제를 추가할 때는 questions.csv에 줄만 추가하면 되고, 코드는 고칠 필요가 없습니다.
#
# 칸 순서: 난이도, 문장, 정답, 오답1, 오답2, 오답3, 세트
#  - 난이도 : 초급 또는 고급
#  - 문장   : 게임에서 음성으로 들려주는 일본어 문장입니다. (정답 공개 때 화면에도 표시됩니다.)
#  - 정답   : 문장의 올바른 한국어 뜻. 보기 순서는 게임에서 매번 자동으로 섞입니다.
#  - 오답1~3 : 나머지 보기 3개
#  - 세트   : 1 이상의 세트 번호. 같은 난이도 안에서 같은 번호끼리 한 세트입니다.
#  - 음성 파일 번호는 questions.csv에 적은 문제 순서(데이터 줄 기준 1번부터)대로 매겨집니다. (001, 002, ...)
# 첫 줄은 제목 줄이라 읽지 않고, 칸 맨 앞이 #으로 시작하는 줄은 메모로 보고 건너뜁니다.
# ===========================================================================
QUESTION_FILE = "questions.csv"
LEVEL_CODES = {"초급": 0, "고급": 1, "0": 0, "1": 1}
LEVEL_LABELS = ("초급", "고급")
# 아래 폭은 화면에 한 줄이 들어가는지 보는 참고용 기준입니다. (전각 글자 1개 = 2, 반각 1개 = 1) 넘어도 빌드는 멈추지 않고 경고만 보여줍니다.
MAX_SENTENCE_WIDTH = 48     # 일본어 문장
MAX_CHOICE_WIDTH = 83       # 보기 한 줄 ("[ ] 1. " 제외)
MAX_NOTE_WIDTH = 86         # 문장 노트 한 줄 ("12. " 제외)
NOTE_MARK_COLOR = "\x1F"    # 문장 노트에서 "="를 표시하는 색 코드
NOTE_TEXT_COLOR = "\x04"


def display_width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def load_questions(path):
    levels = [[], []]
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        raise RuntimeError(f"{path} 파일을 찾을 수 없습니다. build.eds와 같은 폴더에 있어야 합니다.")
    except UnicodeDecodeError:
        raise RuntimeError(f"{path}: UTF-8 형식이 아닙니다. 엑셀에서는 'CSV UTF-8(쉼표로 분리)'로 저장해 주세요.")
    voice_no = 0
    with io.StringIO(text, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # 제목 줄
        for line_no, row in enumerate(reader, start=2):
            cells = [cell.strip() for cell in row]
            if not any(cells) or cells[0].startswith("#"):
                continue
            where = f"{path} {line_no}번째 줄"
            voice_no += 1
            if len(cells) < 7:
                raise RuntimeError(f"{where}: 칸이 7개 필요합니다. (난이도, 문장, 정답, 오답1, 오답2, 오답3, 세트)")
            level_text, sentence, correct, wrong1, wrong2, wrong3, set_text = cells[:7]
            if level_text not in LEVEL_CODES:
                raise RuntimeError(f"{where}: 난이도는 '초급' 또는 '고급'이어야 합니다. (입력값: {level_text!r})")
            for cell in cells[:7]:
                if any(ord(ch) < 32 for ch in cell):
                    raise RuntimeError(f"{where}: 칸 안에 줄바꿈이나 제어 문자가 있습니다.")
            if not sentence:
                raise RuntimeError(f"{where}: 문장이 비어 있습니다.")
            choices = [correct, wrong1, wrong2, wrong3]
            if "" in choices or len(set(choices)) != 4:
                raise RuntimeError(f"{where}: 정답과 오답 3개는 비어 있거나 서로 같으면 안 됩니다.")
            if not set_text.isdigit() or int(set_text) < 1:
                raise RuntimeError(f"{where}: 7번째 칸(세트)에 1 이상의 세트 번호를 적어 주세요. (입력값: {set_text!r})")
            note = f"{sentence} {NOTE_MARK_COLOR}={NOTE_TEXT_COLOR} {correct}"   # 문장 노트 한 줄: 문장 = 뜻
            if display_width(sentence) > MAX_SENTENCE_WIDTH:
                print(f"[경고] {where}: 문장이 깁니다. 화면에 안 맞을 수 있어요.")
            if max(display_width(choice) for choice in choices) > MAX_CHOICE_WIDTH:
                print(f"[경고] {where}: 보기가 깁니다. 화면에 안 맞을 수 있어요.")
            if display_width(f"{sentence} = {correct}") > MAX_NOTE_WIDTH:
                print(f"[경고] {where}: 문장 노트 한 줄이 깁니다. 화면에 안 맞을 수 있어요.")
            levels[LEVEL_CODES[level_text]].append({
                "set": int(set_text),
                "voice": voice_no,
                "sentence": sentence,
                "choices": choices,   # 정답이 항상 첫 번째
                "note": note,
            })
    if not any(levels):
        raise RuntimeError(f"{path}: 문제가 하나도 없습니다.")
    for code, label in enumerate(LEVEL_LABELS):
        if not levels[code]:
            print(f"[경고] {path}: {label} 문제가 없습니다. 게임에서 {label} 난이도를 고르면 낼 문제가 없습니다.")
    return levels


_question_levels = load_questions(QUESTION_FILE)
# 난이도(초급 → 고급) 순서로, 같은 난이도 안에서는 세트 번호 순서로 문제를 정렬합니다. (같은 세트는 연속으로 놓입니다.)
_question_levels = [sorted(level, key=lambda q: q["set"]) for level in _question_levels]
_questions = _question_levels[0] + _question_levels[1]

QuestionSentences = EUDArray([Db(q["sentence"]) for q in _questions])
QuestionChoices = EUDArray([Db(choice) for q in _questions for choice in q["choices"]])   # 문제당 4개 (각 문제의 첫 번째가 정답)
QuestionNotes = EUDArray([Db(q["note"]) for q in _questions])   # 문장 노트용 "문장 = 뜻"
QuestionVoiceNo = EUDArray([q["voice"] for q in _questions])    # 문제별 음성 파일 번호 (questions.csv의 문제 순서, 1부터)
QuestionLevels = EUDArray([0] * len(_question_levels[0]) + [1] * len(_question_levels[1]))   # 문제별 난이도 (0: 초급, 1: 고급)
MaxLevelCount = len(_questions)

# 세트 번호는 1 ~ SetCount. 게임 안에서 세트 0은 "전체 세트"를 뜻합니다.
SetCount = max(q["set"] for q in _questions)
SetStride = SetCount + 1
# 난이도(0: 초급, 1: 고급)와 세트 번호(0: 전체)에 해당하는 문제는 항상 연속된 한 구간입니다.
# 구간 번호 = 난이도 * SetStride + 세트 번호
_pool_first, _pool_count = [], []
_offset = 0
for _level in _question_levels:
    _first_of_level = _offset
    _pool_first.append(_first_of_level)
    _pool_count.append(len(_level))
    for _set_no in range(1, SetCount + 1):
        _members = [k for k, q in enumerate(_level) if q["set"] == _set_no]
        _pool_first.append(_first_of_level + (_members[0] if _members else 0))
        _pool_count.append(len(_members))
    _offset += len(_level)
PoolFirst = EUDArray(_pool_first)
PoolCount = EUDArray(_pool_count)
print(f"[문제 데이터] 초급 {len(_question_levels[0])}문제, 고급 {len(_question_levels[1])}문제, 세트 {SetCount}개를 불러왔습니다.")

# ===========================================================================
# 음성 파일: Map 폴더 옆의 voice 폴더에 있는 001.ogg, 002.ogg, ... 를 맵에 넣습니다.
# 번호는 questions.csv의 문제 순서(1번부터)와 같습니다. (001 = 첫 번째 문제)
# 게임에서는 문제의 음성 번호 N에 해당하는 "voice_N"이라는 이름으로 재생합니다. (flashArithmetic.eps의 playVoice)
# 같은 번호의 파일이 .ogg와 .wav 둘 다 있으면 .ogg를 씁니다. (.mp3는 쓰지 않습니다.)
# ===========================================================================
VOICE_DIR = "../voice"
VOICE_EXTENSIONS = (".ogg", ".wav")


def add_voice_files(count):
    missing = []
    total_bytes = 0
    for voice_no in range(1, count + 1):
        for ext in VOICE_EXTENSIONS:
            path = f"{VOICE_DIR}/{voice_no:03d}{ext}"
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    data = f.read()
                MPQAddFile(f"voice_{voice_no}", data)
                total_bytes += len(data)
                break
        else:
            missing.append(voice_no)
    print(f"[음성 파일] {count - len(missing)}/{count}개를 맵에 넣었습니다. (합계 {total_bytes / 1024 / 1024:.2f}MB)")
    if missing:
        shown = ", ".join(f"{n:03d}" for n in missing[:10]) + (" …" if len(missing) > 10 else "")
        print(f"[경고] {os.path.abspath(VOICE_DIR)} 에서 {len(missing)}개의 .ogg/.wav 파일을 찾지 못했습니다: {shown}")
        mp3_only = [n for n in missing if os.path.isfile(f"{VOICE_DIR}/{n:03d}.mp3")]
        if mp3_only:
            print(f"[경고] 그중 {len(mp3_only)}개는 .mp3만 있습니다. .ogg나 .wav로 변환해 주세요.")


add_voice_files(len(_questions))

init()
