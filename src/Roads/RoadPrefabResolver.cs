using Colossal.Logging;

namespace CityTimelineMod.Roads
{
    public static class RoadPrefabResolver
    {
        public static string ResolvePrefabHint(RoadImportMetadata meta)
        {
            if (meta == null)
            {
                return "unknown";
            }

            if (meta.Roundabout)
            {
                return "roundabout";
            }

            switch (meta.Highway)
            {
                case "motorway":
                case "trunk":
                    return meta.Oneway
                        ? "highway-oneway"
                        : "highway";

                case "primary":
                case "secondary":
                    return meta.TargetLaneCount >= 4
                        ? "avenue"
                        : "large-road";

                case "tertiary":
                case "residential":
                    return "medium-road";

                case "service":
                    return "service-road";

                default:
                    return "basic-road";
            }
        }
    }
}
