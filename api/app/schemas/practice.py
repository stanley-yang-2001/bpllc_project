"""Response and request models: practice material and remembered answers."""
from __future__ import annotations


from datetime import date, datetime

from pydantic import BaseModel, Field


class Preview(BaseModel):
    """Seconds until the word comes back for each answer, so the buttons can say "10m" or "3d"."""
    again: int
    hard: int
    good: int
    easy: int


class FlashcardOut(BaseModel):
    id: int
    word: str
    meaning: str
    status: str                         # new, learning, relearning, young, mature
    ease: float
    interval_days: float
    lapses: int
    reps: int
    leech: bool                         # forgotten many times: worth a better way to remember it
    due_at: datetime | None             # null: never practised
    preview: Preview


class FlashcardSet(BaseModel):
    items: list[FlashcardOut]
    total: int                          # cards in the chosen scope (the round may be shorter if a limit was asked for)
    selection: int                      # words with a meaning in the chosen sets
    due: int                            # of those, practised before and due now
    new: int                            # never practised


class PosCard(BaseModel):
    id: int
    word: str
    answer: str
    options: list[str]
    meaning: str | None = None


class PosSet(BaseModel):
    items: list[PosCard]
    total: int


class DictationOut(BaseModel):
    id: int
    word: str
    meaning: str | None = None


class DictationSet(BaseModel):
    items: list[DictationOut]
    total: int


class ChoiceOut(BaseModel):
    id: int
    prompt: str
    answer: str
    choices: list[str]
    direction: str


class ChoiceSet(BaseModel):
    items: list[ChoiceOut]
    total: int


class AnswerIn(BaseModel):
    word_id: int
    correct: bool
    think_ms: int | None = Field(None, ge=0, le=3_600_000)           # until the learner chose or checked the answer
    mode: str = Field("flashcards", max_length=12)
    direction: str | None = Field(None, max_length=8)


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=50)


class ReviewIn(BaseModel):
    word_id: int
    grade: int = Field(ge=1, le=4)                                  # 1 again, 2 hard, 3 good, 4 easy
    think_ms: int | None = Field(None, ge=0, le=3_600_000)          # card shown until the learner checked the answer
    rate_ms: int | None = Field(None, ge=0, le=3_600_000)           # answer shown until the learner graded it
    mode: str = Field("flashcards", max_length=12)
    direction: str | None = Field(None, max_length=8)               # "word" (see the word) or "meaning" (see the meaning)


class ReviewsIn(BaseModel):
    reviews: list[ReviewIn] = Field(max_length=50)


class ReviewResult(BaseModel):
    word_id: int
    delay_seconds: int                  # until the word is due again
    status: str
    counted: bool                       # False: practised early and remembered, the schedule stayed
    correct: bool
    box: int
    ease: float
    interval_days: float
    lapses: int
    preview: Preview                    # what each answer would schedule next, so a word that comes back in this session shows the right times


class ReviewResults(BaseModel):
    results: list[ReviewResult]


class StatsDay(BaseModel):
    day: date
    reviews: int
    correct: int
    avg_think_ms: int | None = None


class ForecastDay(BaseModel):
    day: date
    due: int


class StudyStats(BaseModel):
    language: str
    words: int                          # words with a meaning in the chosen sets
    new: int
    learning: int
    relearning: int
    young: int
    mature: int
    due_now: int
    leeches: int
    reviews_30d: int
    accuracy_30d: float | None = None   # share of answers that were not "again"
    retention_30d: float | None = None  # of the reviews that were due, how many were remembered
    avg_think_ms: int | None = None
    median_think_ms: int | None = None
    avg_rate_ms: int | None = None
    studied_seconds_30d: int
    today_reviews: int
    total_reviews: int                  # everything ever answered in the chosen sets
    total_words_practised: int
    total_days: int                     # days with at least one answer
    total_accuracy: float | None = None
    total_retention: float | None = None
    total_avg_think_ms: int | None = None
    total_studied_seconds: int
    days: list[StatsDay]
    forecast: list[ForecastDay]


class HardWord(BaseModel):
    id: int
    word: str
    meaning: str | None = None
    score: int                          # 0 (easy) to 100 (hardest), from this learner's own answers
    reasons: list[str]                  # often_missed, slow, lapses, low_ease, leech
    reviews: int
    miss_rate: float
    avg_think_ms: int | None = None
    lapses: int
    ease: float
    status: str
    due_at: datetime | None = None


class HardWords(BaseModel):
    items: list[HardWord]
    typical_think_ms: int | None = None


class ProgressOut(BaseModel):
    language: str
    new: int                    # words with a meaning never practised yet
    learning: int               # practised, not yet in box 4
    known: int                  # box 4 or 5
    due: int                    # practised and due now (new words are not counted here)
    streak: int                 # days in a row, UTC days
    practised_today: bool


class ClozeItem(BaseModel):
    before: str
    after: str
    answer: str
    hint: str
    choices: list[str]
    word_id: int | None = None          # the learner's word this blank is for, so the answer can be remembered


class ClozeSet(BaseModel):
    story_id: int
    language: str
    items: list[ClozeItem]
