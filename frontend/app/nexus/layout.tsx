import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TAO Nexus — AI Cloud Economics Operating System",
  description:
    "Enterprise cloud cost intelligence, optimization, and decision support. Built by the TAO Team at Discount Tire.",
};

export default function NexusLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
