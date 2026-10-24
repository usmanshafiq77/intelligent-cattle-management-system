import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { cattleErrorMessage } from "../cattleErrors";
import { CATTLE_STATUSES, optionLabel, SEXES } from "../cattleOptions";
import { CattlePage } from "../components/CattlePage";
import { OptionField } from "../components/OptionField";
import { useCattleCollection } from "../hooks/useCattleCollection";

const PAGE_SIZE = 20;

export function CattleListScreen({ onBack, onCreate, onOpen, api = cattleApi }) {
  const farm = useFarm();
  return <RequireFarm><RequirePermission permission="cattle.view"><ListContent farm={farm} onBack={onBack} onCreate={onCreate} onOpen={onOpen} api={api} /></RequirePermission></RequireFarm>;
}

function ListContent({ farm, onBack, onCreate, onOpen, api }) {
  const { theme, spacing, typography } = useAppTheme();
  const [search, setSearch] = useState("");
  const [sex, setSex] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(0);
  const query = useMemo(() => ({
    search: search.trim() || undefined,
    sex: sex || undefined,
    status: status || undefined,
    sort,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }), [page, search, sex, sort, status]);
  const collection = useCattleCollection({ farmId: farm.activeFarm.id, enabled: farm.can("cattle.view"), query, api });
  const pageCount = Math.max(1, Math.ceil(collection.total / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const visible = collection.animals;
  const resetPage = (setter) => (value) => { setter(value); setPage(0); };

  return (
    <CattlePage title="Cattle directory" subtitle={`Verified records for ${farm.activeFarm.name}.`} onBack={onBack} action={farm.can("cattle.create") ? <AppButton title="Register cattle" size="small" fullWidth={false} onPress={onCreate} /> : null}>
      <View style={{ gap: spacing.lg }}>
        <AppInput testID="cattle-search" label="Search herd" placeholder="Name or tag number" value={search} onChangeText={resetPage(setSearch)} />
        <OptionField label="Sex filter" value={sex} options={["", ...SEXES]} onChange={resetPage(setSex)} />
        <OptionField label="Status filter" value={status} options={["", ...CATTLE_STATUSES]} onChange={resetPage(setStatus)} />
        <OptionField label="Sort" value={sort} options={["recent", "tag", "name"]} onChange={resetPage(setSort)} />
        {collection.status === "loading" ? <FeedbackState type="loading" title="Loading cattle" message="Fetching the active farm's cattle records." showSkeleton /> : null}
        {collection.status === "error" ? <FeedbackState type="error" title="Cattle unavailable" message={cattleErrorMessage(collection.error)} actionLabel="Retry" onAction={() => { void collection.refresh(); }} /> : null}
        {collection.status === "ready" && !collection.animals.length ? <FeedbackState title="No cattle registered" message="This farm has no cattle records yet." actionLabel={farm.can("cattle.create") ? "Register first animal" : undefined} onAction={farm.can("cattle.create") ? onCreate : undefined} /> : null}
        {collection.status === "ready" && collection.animals.length && !visible.length ? <FeedbackState title="No matching cattle" message="Adjust the search or filters to see other records." actionLabel="Clear filters" onAction={() => { setSearch(""); setSex(""); setStatus(""); setPage(0); }} compact /> : null}
        <View style={styles.grid}>
          {visible.map((animal) => (
            <AppCard key={animal.id} testID={`cattle-card-${animal.id}`} title={animal.name || animal.tag_number} subtitle={`Tag ${animal.tag_number}`} overline={animal.breed?.name || optionLabel(animal.species)} onPress={() => onOpen?.(animal.id)} accessibilityLabel={`Open cattle ${animal.name || animal.tag_number}`} style={styles.card}>
              <View style={styles.cardMeta}>
                <StatusBadge status={animal.status === "ACTIVE" ? "success" : "info"} label={optionLabel(animal.status)} compact />
                <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.small }}>{optionLabel(animal.sex)} · {optionLabel(animal.category)}</Text>
                <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.small }}>{animal.latest_weight ? `${animal.latest_weight.weight_kg} kg` : "No weight recorded"}</Text>
              </View>
            </AppCard>
          ))}
        </View>
        {collection.status === "ready" && collection.total ? <View style={styles.pagination}>
          <AppButton title="Previous" variant="outline" size="small" fullWidth={false} disabled={safePage === 0} onPress={() => setPage((value) => Math.max(0, value - 1))} />
          <Text accessibilityLabel={`Page ${safePage + 1} of ${pageCount}`} style={{ color: theme.colors.text }}>Page {safePage + 1} of {pageCount}</Text>
          <AppButton title="Next" variant="outline" size="small" fullWidth={false} disabled={collection.complete} onPress={() => setPage((value) => Math.min(pageCount - 1, value + 1))} />
          <Pressable accessibilityRole="button" onPress={() => { void collection.refresh(); }}><Text style={{ color: theme.colors.primary, fontWeight: typography.weights.bold, padding: spacing.md }}>Refresh</Text></Pressable>
        </View> : null}
      </View>
    </CattlePage>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 14 },
  card: { minWidth: 260, flexBasis: 320, flexGrow: 1 },
  cardMeta: { gap: 10 },
  pagination: { flexDirection: "row", flexWrap: "wrap", gap: 12, alignItems: "center", justifyContent: "center" },
});
