import type { Metadata } from "next";
import "../styles/globals.css";
import { QueryProvider } from "@/lib/query-provider";
import { AuthProvider } from "@/lib/auth-context";
import { I18nProvider } from "@/lib/i18n-context";
import { GlobalErrorListener } from "@/components/GlobalErrorListener";
import { HtmlLangSetter } from "@/components/HtmlLangSetter";
import { AgentChatBar } from "@/components/AgentChatBar";

export const metadata: Metadata = {
  title: "BHOOMI — Agriculture Intelligence Platform",
  description:
    "BHOOMI combines farm, soil, satellite, weather and crop-disease information into localized, evidence-backed decision support, with a cooperation layer for agricultural models across states.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/logo.jpeg" type="image/jpeg" />
      </head>
      <body className="bg-background text-text-primary antialiased">
        <GlobalErrorListener />
        <I18nProvider>
          <HtmlLangSetter />
          <QueryProvider>
            <AuthProvider>
              {children}
              {/* Auth-aware, so it renders nothing until someone signs in. */}
              <AgentChatBar />
            </AuthProvider>
          </QueryProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
