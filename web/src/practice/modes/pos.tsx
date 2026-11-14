import { Tags } from "lucide-react";
import { useI18n } from "../../i18n/I18nProvider";
import { Button } from "../../components/ui";
import { PosPractice } from "../PosPractice";
import { ModeTile } from "./ModeTile";
import type { PracticeMode } from "./types";

export const PosMode: PracticeMode<"pos"> = {
  Tile({ start }) {
    const { t } = useI18n();
    return (
      <ModeTile icon={Tags} title={t("practice.pos.title")} text={t("practice.pos.text")}>
        <Button onClick={() => start({ mode: "pos" })}>{t("practice.pos.start")}</Button>
      </ModeTile>
    );
  },
  Session: ({ ctx, onDone }) => <PosPractice language={ctx.language} set={ctx.set} due={ctx.dueOnly} onDone={onDone} />,
};
