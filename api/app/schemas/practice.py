"""Response and request models: practice material and remembered answers."""
from __future__ import annotations


from datetime import date, datetime

from pydantic import BaseModel, Field

from .words import PictureOut


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
    picture: PictureOut | None = None   # shown with the meaning when the card is turned over


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
    picture: PictureOut | None = None   # direction "picture": what the learner sees (the prompt is then only the meaning, for screen readers)


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


class StreakOut(BaseModel):
    days: int                   # practised days in a row; one missed day a week is forgiven
    alive: bool
    practised_today: bool
    rest_available: bool        # a missed day would be forgiven right now
    rest_used_on: date | None = None
    best: int


class GoalOut(BaseModel):
    target: int
    done: int
    reached: bool
    left: int


class WeekOut(BaseModel):
    days_practised: int         # of the last 7 days
    answers: int
    words_learned: int          # words that reached "known" in the last 7 days
    stories_saved: int
    due_now: int
    new_words: int


class BadgeOut(BaseModel):
    id: str
    earned: bool
    have: int
    target: int


class ComebackOut(BaseModel):
    days_away: int              # days since the practice before this one
    returned: bool              # has practised today


class BestDayOut(BaseModel):
    value: int
    day: date


class RecordsOut(BaseModel):
    best_day: BestDayOut | None = None     # most answers in one day
    longest_run: int                       # most right answers in a row (anything but Again)
    fastest_ms: int | None = None          # best day's average think time, days with 10+ answers
    best_week_learned: int                 # most words that reached Known in one calendar week


class StoryWordsOut(BaseModel):
    used: int                   # words of this language that appear in a saved story
    total: int


class ChallengeOut(BaseModel):
    id: str                     # learn_words, practise_days, answer_cards or save_stories
    have: int
    target: int
    done: bool
    ends_on: date               # the Sunday this week's challenge ends


class GardenOut(BaseModel):
    seeds: int                  # words not practised yet
    sprouts: int                # words being learned
    trees: int                  # words that are Known


class RewardsOut(BaseModel):
    show_rewards: bool
    streak: StreakOut
    goal: GoalOut
    week: WeekOut
    known_words: int
    comeback: ComebackOut | None = None
    challenge: ChallengeOut
    garden: GardenOut
    records: RecordsOut
    story_words: StoryWordsOut
    badges: list[BadgeOut]
    next_badge: BadgeOut | None = None
