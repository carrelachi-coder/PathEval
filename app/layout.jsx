import "./globals.css";

export const metadata = {
  title: "PathEval",
  description: "AI-generated pathology image evaluation",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
