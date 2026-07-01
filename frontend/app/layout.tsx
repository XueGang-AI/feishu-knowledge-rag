import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Feishu Knowledge RAG",
  description: "Local Feishu knowledge base RAG",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg"
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
