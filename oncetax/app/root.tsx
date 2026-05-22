import type { LinksFunction, MetaFunction } from "@remix-run/cloudflare";
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "@remix-run/react";

import tailwindHref from "./tailwind.css?url";

export const links: LinksFunction = () => [
  { rel: "stylesheet", href: tailwindHref },
  { rel: "icon", href: "/favicon.ico" },
];

export const meta: MetaFunction = () => [
  { title: "OnceTax — Sales tax filing prep for Shopify" },
  {
    name: "description",
    content:
      "OnceTax generates state-by-state sales tax filing prep PDFs from your Shopify orders. No auto-filing in v0.",
  },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body className="h-full bg-slate-50 text-slate-900 antialiased">
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}
