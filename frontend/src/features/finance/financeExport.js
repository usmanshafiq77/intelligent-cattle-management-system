import { Platform } from "react-native";

export async function deliverFinanceExport(blob, filename, format) {
  if (Platform.OS === "web") {
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(href);
    return "downloaded";
  }

  const [{ File, Paths }, Sharing] = await Promise.all([
    import("expo-file-system"),
    import("expo-sharing"),
  ]);
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error("File sharing is unavailable on this device.");
  }
  const file = new File(Paths.cache, filename);
  file.create({ overwrite: true, intermediates: true });
  file.write(new Uint8Array(await blob.arrayBuffer()));
  await Sharing.shareAsync(file.uri, {
    dialogTitle: `Share ${filename}`,
    mimeType: format === "pdf"
      ? "application/pdf"
      : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  return "shared";
}
