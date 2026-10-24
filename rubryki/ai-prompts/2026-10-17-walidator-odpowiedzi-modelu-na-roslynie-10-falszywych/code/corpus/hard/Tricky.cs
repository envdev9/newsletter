namespace Hard
{
    public class Outer
    {
        public class Inner
        {
            public int Depth() => 1;
        }

        public int AfterInner() => 2;

        public int Width;

        public event EventHandler? Changed;
    }

    public static class Parser
    {
        /* public static int Commented() => 0; */
        public static int Parse(string s) => int.Parse(s);

        // public static int Ghost(string s) => 0;
        private static int Helper(string s) => s.Length;

        public static T Convert<T>(string s) where T : struct => default;

        public static async Task<int> LoadAsync(CancellationToken ct = default)
        {
            await Task.Delay(1, ct);
            int Local() => 3;
            return Local();
        }
    }
}
