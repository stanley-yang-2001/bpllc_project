import { useEffect, useState } from "react";
import { speechSupported } from "./speak";

/** The device's voice list as state. Browsers (Chrome especially) fill it in late and announce it with `voiceschanged`. */
export function useVoices(): SpeechSynthesisVoice[] {
  const read = () => (speechSupported() ? window.speechSynthesis.getVoices() : []);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(read);
  useEffect(() => {
    if (!speechSupported()) return;
    const synth = window.speechSynthesis;
    const update = () => setVoices(synth.getVoices());
    update();
    synth.addEventListener?.("voiceschanged", update);
    return () => synth.removeEventListener?.("voiceschanged", update);
  }, []);
  return voices;
}
