import { Platform } from "react-native";

export function milkRowsToCsv(rows) {
  const headers = ["cattle_id", "milking_date", "session_kind", "volume_liters", "lactation_number", "days_in_milk", "fat_percent", "snf_percent", "protein_percent"];
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return [headers, ...rows.map((row) => headers.map((key) => row[key]))]
    .map((row) => row.map(quote).join(","))
    .join("\n");
}

export async function deliverMilkCsv(csv, filename) {
  if (Platform.OS === "web") {
    const href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(href);
    return "downloaded";
  }
  const [{ File, Paths }, Sharing] = await Promise.all([import("expo-file-system"), import("expo-sharing")]);
  if (!(await Sharing.isAvailableAsync())) throw new Error("File sharing is unavailable on this device.");
  const file = new File(Paths.cache, filename);
  file.create({ overwrite: true, intermediates: true });
  file.write(csv);
  await Sharing.shareAsync(file.uri, { dialogTitle: `Share ${filename}`, mimeType: "text/csv" });
  return "shared";
}
