import { AppCard } from "../../../components/ui/AppCard";

export function ShowcaseSection({ title, description, children, entranceDelay = 0 }) {
  return (
    <AppCard
      title={title}
      subtitle={description}
      variant="elevated"
      entranceDelay={entranceDelay}
    >
      {children}
    </AppCard>
  );
}
