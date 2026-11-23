import { ListChecks } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { Button, inputCls } from "../../components/ui";
import { Choices, type Direction } from "../Choices";
import { ModeTile } from "./ModeTile";
import type { PracticeMode } from "./types";

export const ChoiceMode: PracticeMode<"choice"> = {
  Tile({ start }) {
    const { t } = useI18n();
    const [direction, setDirection] = useState<Direction>("meaning");
    return (
      <ModeTile icon={ListChecks} title={t("practice.choice.title")} text={t("practice.choice.text")}>
        <div>
          <label htmlFor="practice-direction" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.choice.direction")}</label>
          <select id="practice-direction" className={inputCls} value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
            <option value="meaning">{t("practice.choice.dirMeaning")}</option>
            <option value="word">{t("practice.choice.dirWord")}</option>
            <option value="picture">{t("pictures.dir")}</option>
          </select>
        </div>
        <Button onClick={() => start({ mode: "choice", direction })}>{t("practice.choice.start")}</Button>
      </ModeTile>
    );
  },
  Session: ({ ctx, launch, onDone }) => <Choices language={ctx.language} set={ctx.set} direction={launch.direction} due={ctx.dueOnly} onDone={onDone} />,
};
