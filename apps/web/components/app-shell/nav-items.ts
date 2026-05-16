import { Briefcase, Settings, Users, type LucideIcon } from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Casa o item ativo por prefixo de path. */
  match: (pathname: string) => boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    label: "Vagas",
    href: "/jobs",
    icon: Briefcase,
    match: (p) => p === "/jobs" || p.startsWith("/jobs/"),
  },
  {
    label: "Candidatos",
    href: "/candidates",
    icon: Users,
    match: (p) => p === "/candidates" || p.startsWith("/candidates/"),
  },
  {
    label: "Configurações",
    href: "/settings/organization",
    icon: Settings,
    match: (p) => p.startsWith("/settings"),
  },
];
