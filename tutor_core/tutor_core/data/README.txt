everyday_<code>.txt: the 6000 most frequent words (as the language's own tokenizer writes them) of English, Spanish, French, German,
Italian, Portuguese, Japanese, Chinese and Korean, one per line, lower case, extracted on 24 Oct 2026 from the open-source wordfreq
package (https://github.com/rspeer/wordfreq; its data is licensed CC BY-SA 4.0, its code Apache 2.0).
Used (tutor_core/difficulty.py) to measure the share of uncommon words in a story, and (tutor_core/quality.py) so that an everyday
word outside a learner's list is not counted as a stray. Chinese, Japanese and Korean are looked up word by word after
tutor_core/splitter.py has split the text. A learner's own list words are never counted as uncommon, so adding an everyday word
to your vocabulary is always allowed and simply makes it "yours".
