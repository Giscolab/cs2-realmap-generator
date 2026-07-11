using Newtonsoft.Json.Linq;

namespace CityTimelineMod.Roads
{
    public static class RuntimeRoadSpawner
    {
        public static void AnalyzeRoadFeature(JObject feature)
        {
            var meta = RoadImportMetadata.FromFeature(feature);

            if (meta == null)
            {
                return;
            }

            var prefabHint = RoadPrefabResolver.ResolvePrefabHint(meta);

            Util.Log.Info(
                $"[RoadImport] highway={meta.Highway} " +
                $"lanes={meta.TargetLaneCount} " +
                $"oneway={meta.Oneway} " +
                $"prefab={prefabHint}"
            );
        }
    }
}
