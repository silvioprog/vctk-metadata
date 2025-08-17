import glob
import os
import re
import subprocess
import sys
from datetime import datetime

from tqdm import tqdm

DIST_DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else "dist"
TMP_DIR = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else "tmp"


def punctuate(text):
    # Fix spaces before commas
    text = re.sub(r"\s+,", ",", text)
    # Handle commas followed by multiple spaces and capital letters
    text = re.sub(r",(\s{2,})([A-Z])", lambda m: ", " + m.group(2).lower(), text)
    # Normalize multiple spaces to single space
    text = re.sub(r"\s{2,}", " ", text)
    # Add space after comma if missing
    text = re.sub(r",([^\s])", r", \1", text)
    # Fix multiple spaces after comma
    text = re.sub(r",\s{2,}", ", ", text)
    # Add space after sentence endings before capital letters
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)
    # Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    # Add period if missing
    if text and text[-1] not in ".!?":
        text += "."
    # Remove trailing spaces after punctuation
    text = re.sub(r"([.!?])\s+$", r"\1", text)
    return text


def parse_wav_files():
    wav_files = glob.glob(f"{TMP_DIR}/wav48_silence_trimmed/*/*_mic1.flac")
    wavs = []
    for wav_file in wav_files:
        relative_path = wav_file[len(TMP_DIR) + 1 :]
        speaker_id = relative_path.split("/")[1]
        filename = relative_path.split("/")[2]
        sequence = filename.split("_")[1]
        wavs.append((speaker_id, sequence))
    return wavs


def parse_speakers():
    speakers = []
    with open(f"{TMP_DIR}/speaker-info.txt", "r") as f:
        next(f)
        for line in f:
            if line.strip():
                parts = line.split()
                if len(parts) >= 3:
                    id = parts[0].strip()
                    age = parts[1].strip()
                    gender = parts[2].strip()
                    accent = parts[3].strip() if len(parts) > 3 else ""
                    region = ""
                    if len(parts) > 4:
                        potential_region = parts[4]
                        if "(" not in potential_region:
                            region = potential_region.strip()
                    speakers.append((id, age, gender, accent, region))
    return speakers


def parse_transcripts():
    wavs = parse_wav_files()
    transcripts = []

    txt_files = glob.glob(f"{TMP_DIR}/txt/*/*.txt")
    for txt_file in txt_files:
        with open(txt_file, "r") as f:
            parts = txt_file[len(TMP_DIR) + 1 :].split("/")
            speaker_id = parts[1]
            ids = parts[2].split("_")
            sequence = ids[1].split(".")[0]
            transcript = punctuate(f.read().strip())
            if (speaker_id, sequence) not in wavs:
                continue
            transcripts.append((speaker_id, sequence, transcript))
    return transcripts


def generate_sql():
    speakers = parse_speakers()
    transcripts = parse_transcripts()

    schema_content = []
    schema_content.append("-- -- VCTK-Corpus Database Schema")
    schema_content.append("-- Generated on: " + datetime.now().strftime("%Y-%m-%d"))
    schema_content.append("")

    schema_content.append("PRAGMA foreign_keys = ON;")
    schema_content.append("")

    schema_content.append("-- Create speakers table")
    schema_content.append("CREATE TABLE speakers (")
    schema_content.append("  id TEXT PRIMARY KEY NOT NULL,")
    schema_content.append("  age INTEGER NOT NULL,")
    schema_content.append("  gender TEXT NOT NULL,")
    schema_content.append("  accent TEXT NOT NULL,")
    schema_content.append("  region TEXT")
    schema_content.append(");")
    schema_content.append("")

    schema_content.append("-- Create transcripts table")
    schema_content.append("CREATE TABLE transcripts (")
    schema_content.append("  speaker_id TEXT NOT NULL,")
    schema_content.append("  sequence TEXT NOT NULL,")
    schema_content.append("  transcript TEXT NOT NULL,")
    schema_content.append("  UNIQUE (speaker_id, sequence),")
    schema_content.append("  FOREIGN KEY (speaker_id) REFERENCES speakers(id)")
    schema_content.append(");")
    schema_content.append("")

    schema_content.append("-- Insert speakers data")
    speaker_values = []
    for id, age, gender, accent, region in speakers:
        speaker_values.append(f"('{id}', {age}, '{gender}', '{accent}', '{region}')")
    schema_content.append("INSERT INTO speakers (id, age, gender, accent, region)")
    schema_content.append("VALUES")
    schema_content.append("  " + ",\n  ".join(speaker_values) + ";")
    schema_content.append("")

    with open(f"{DIST_DIR}/01_schema.sql", "w") as f:
        f.write("\n".join(schema_content))

    chunk_size = 1500
    transcript_chunks = [
        transcripts[i : i + chunk_size] for i in range(0, len(transcripts), chunk_size)
    ]

    for i, chunk in enumerate(transcript_chunks):
        chunk_content = []
        chunk_content.append(
            f"-- -- Transcript chunk {i+1} of {len(transcript_chunks)}"
        )
        chunk_content.append(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d')}")
        chunk_content.append("")

        chunk_content.append("-- Insert transcripts data")
        transcription_values = []
        for speaker_id, sequence, transcript in chunk:
            transcription_values.append(
                f"('{speaker_id}', '{sequence}', '{transcript.replace("'", "''")}')"
            )
        chunk_content.append(
            "INSERT INTO transcripts (speaker_id, sequence, transcript)"
        )
        chunk_content.append("VALUES")
        chunk_content.append("  " + ",\n  ".join(transcription_values) + ";")
        chunk_content.append("")

        with open(f"{DIST_DIR}/02_transcripts_{i+1:03d}.sql", "w") as f:
            f.write("\n".join(chunk_content))

    indexes_content = []
    indexes_content.append("-- -- Indexes for VCTK-Corpus Database")
    indexes_content.append("-- Generated on: " + datetime.now().strftime("%Y-%m-%d"))
    indexes_content.append("")

    indexes_content.append("-- Index for speaker information lookups")
    indexes_content.append("CREATE INDEX idx_speakers_id ON speakers(id);")
    indexes_content.append("")

    indexes_content.append(
        "-- Composite index for speaker+transcript lookups and unique constraint"
    )
    indexes_content.append(
        "CREATE INDEX idx_transcripts_speaker_id_sequence ON transcripts(speaker_id, sequence);"
    )
    indexes_content.append("")

    with open(f"{DIST_DIR}/03_indexes.sql", "w") as f:
        f.write("\n".join(indexes_content))

    return transcripts


def convert_to_mp3(transcripts):
    wavs = [(wav[0], wav[1]) for wav in transcripts]
    for speaker_id, sequence in tqdm(
        wavs, desc="Converting FLAC files to MP3", unit="file"
    ):
        wav_file = f"{TMP_DIR}/wav48_silence_trimmed/{speaker_id}/{speaker_id}_{sequence}_mic1.flac"
        mp3_file = f"{DIST_DIR}/{speaker_id}/{sequence}.mp3"
        os.makedirs(os.path.dirname(mp3_file), exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                wav_file,
                "-loglevel",
                "error",
                "-codec:a",
                "mp3",
                "-q:a",
                "4",
                "-y",
                mp3_file,
            ]
        )


if __name__ == "__main__":
    transcripts = generate_sql()
    convert_to_mp3(transcripts)
