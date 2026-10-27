import type { Metadata } from "next";
import { DraftMemory } from "@/components/draft-memory";
import "./globals.css";
export const metadata: Metadata = {
  title: "Alojan · Kişisel agentlerin",
  description: "Ses agentlerini oluştur, düzenle ve yönet.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr">
      <body>
        <DraftMemory>{children}</DraftMemory>
      </body>
    </html>
  );
}
