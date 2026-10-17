namespace Hard;

public static class Platform
{
#if LEGACY_WIN
    public static string Name() => "win";
#else
    public static string Name() => "other";
#endif

#if LEGACY_WIN
    public static int OnlyWin() => 1;
#endif
}
