import "./globals.css";

export const metadata = {
  title: "PathEval",
  description: "AI-generated pathology image evaluation",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
