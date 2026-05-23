using Newtonsoft.Json.Linq;

namespace CityTimelineMod.Roads
{
    public sealed class RoadImportMetadata
    {
        public string Highway { get; set; } = "";
        public string Subcategory { get; set; } = "";
        public int TargetLaneCount { get; set; } = 1;
        public bool Oneway { get; set; }
        public bool Roundabout { get; set; }
        public bool Bridge { get; set; }
        public bool Tunnel { get; set; }
        public string Maxspeed { get; set; } = "";
        public string Surface { get; set; } = "";

        public static RoadImportMetadata FromFeature(JObject feature)
        {
            var props = feature["properties"] as JObject;
            var roadImport = props?["roadImport"] as JObject;

            if (roadImport == null)
            {
                return null;
            }

            return new RoadImportMetadata
            {
                Highway = roadImport.Value<string>("highway") ?? "",
                Subcategory = roadImport.Value<string>("subcategory") ?? "",
                TargetLaneCount = roadImport.Value<int?>("targetLaneCount") ?? 1,
                Oneway = roadImport.Value<bool?>("oneway") ?? false,
                Roundabout = roadImport.Value<bool?>("roundabout") ?? false,
                Bridge = roadImport.Value<bool?>("bridge") ?? false,
                Tunnel = roadImport.Value<bool?>("tunnel") ?? false,
                Maxspeed = roadImport.Value<string>("maxspeed") ?? "",
                Surface = roadImport.Value<string>("surface") ?? "",
            };
        }

        public override string ToString()
        {
            return $"{Highway} lanes={TargetLaneCount} oneway={Oneway}";
        }
    }
}
