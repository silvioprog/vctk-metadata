# VCTK-Corpus Metadata Generator

Processes the VCTK-Corpus speech synthesis dataset and generates a SQLite database schema with speakers and transcripts.

## Quick Start

```bash
./run.sh
```

## What it does

- Downloads VCTK-Corpus dataset from Edinburgh DataShare
- Parses speaker information and transcript files
- Applies punctuation normalization to transcripts
- Generates SQLite database schema with speakers and transcripts
- Converts FLAC files to MP3 format

## Requirements

- Python 3.10+
- FFmpeg
- wget
- sqlite3 (for local testing)

## Output

- `dist/01_schema.sql` - Database schema and initial data (speakers)
- `dist/02_transcripts_*.sql` - Transcript data split into chunks of 1500 records
- `dist/03_indexes.sql` - Database indexes for performance optimization
- `dist/` - MP3 audio files (converted from FLAC)

## Local Database Testing

You can test the generated SQL files locally using sqlite3:

```bash
# Import all SQL files into a local database
cat dist/01_schema.sql dist/02_transcripts_*.sql dist/03_indexes.sql | sqlite3 vctk-corpus.db

# Verify the data
sqlite3 vctk-corpus.db "SELECT COUNT(*) FROM transcripts; SELECT COUNT(*) FROM speakers;"
```

## Cloudflare Deployment

To deploy to Cloudflare D1 (database) and R2 (audio storage):

```bash
./publish.sh
```

This script will:

1. **Create D1 database** `vctk-corpus` if it doesn't exist
2. **Execute all SQL files** to populate the database with metadata
3. **Create R2 bucket** `vctk-corpus` if it doesn't exist  
4. **Upload all MP3 files** to R2, preserving the directory structure

The deployment creates a complete cloud setup with:

- **Structured metadata** in D1 (speakers and transcripts)
- **Audio files** in R2 (MP3 files organized by speaker ID)

## Database Schema

The generated database contains two main tables:

### Speakers Table

```sql
CREATE TABLE speakers (
  id TEXT PRIMARY KEY NOT NULL, -- Speaker ID (e.g., 'p225')
  age INTEGER NOT NULL,         -- Speaker age
  gender TEXT NOT NULL,         -- Speaker gender ('M' or 'F')
  accent TEXT NOT NULL,         -- Speaker accent (e.g., 'English', 'Scottish')
  region TEXT                   -- Geographic region (e.g., 'Southern')
);
```

### Transcripts Table

```sql
CREATE TABLE transcripts (
  speaker_id TEXT NOT NULL,             -- Speaker ID (foreign key)
  sequence TEXT NOT NULL,               -- Transcript sequence
  transcript TEXT NOT NULL,             -- Transcript text
  UNIQUE (speaker_id, sequence),        -- Ensures uniqueness
  FOREIGN KEY (speaker_id) REFERENCES speakers(id)
);
```

## Usage Examples

### Get a Random Transcript

```sql
SELECT
  t.transcript,
  t.sequence,
  t.speaker_id AS speaker,
  s.age,
  s.gender,
  s.accent,
  s.region
FROM transcripts AS t
INNER JOIN speakers AS s ON t.speaker_id = s.id
-- To exclude multiple sequences per speaker:
-- WHERE NOT (
--   (t.speaker_id = 'p225' AND t.sequence IN ('001', '003', '015')) OR
--   (t.speaker_id = 'p226' AND t.sequence IN ('002', '007', '021')) OR
--   (t.speaker_id = 'p227' AND t.sequence IN ('005', '012'))
-- )
ORDER BY RANDOM()
LIMIT 1;
```

### Get All Transcripts for a Speaker

```sql
SELECT * FROM transcripts WHERE speaker_id = 'p225';
```

### Get Speakers by Accent

```sql
SELECT * FROM speakers WHERE accent = 'Scottish';
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
