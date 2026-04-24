import Link from "next/link";
import "./globals.css";
import { ResearchOnlyBanner } from "@/components/ResearchOnlyBanner";

export const metadata = {
  title: "Betfair Research Platform",
  description: "Research-only / paper-trading-only. No real orders.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body className="min-h-screen bg-bg text-fg">
        <ResearchOnlyBanner />
        <header className="border-b border-line">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="font-semibold">
              Betfair Research Platform
            </Link>
            <nav className="flex gap-5 text-sm text-muted">
              <Link href="/" className="hover:text-fg">Dashboard</Link>
              <Link href="/opportunities" className="hover:text-fg">Opportunità</Link>
              <Link href="/setup" className="hover:text-fg">Setup</Link>
              <Link href="/compliance" className="hover:text-fg">Compliance</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
        <footer className="border-t border-line mt-10 py-6 text-center text-xs text-muted">
          Research platform · Paper trading only · Non è consulenza finanziaria · v1.0.0
        </footer>
      </body>
    </html>
  );
}
