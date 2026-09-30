"use client";

import { useEffect } from "react";
import { useI18n } from "@/lib/i18n-context";

/**
 * Sets the <html> element's lang and dir attributes based on
 * the currently selected language from the i18n context.
 */
export function HtmlLangSetter() {
  const { lang, dir } = useI18n();

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  return null;
}
