import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { ToastProvider } from "@/components/toast-notifications";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "RANTAS - Rapid Anti-phishing Network Takedown Analysis System",
  description: "Automated phishing takedown system with OSINT analysis and email reporting",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased">
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
