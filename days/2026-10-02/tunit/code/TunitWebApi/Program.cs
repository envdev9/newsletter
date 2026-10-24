using System.Security.Claims;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using TunitWebApi;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        // MapInboundClaims = false: nie tlumacz krotkich nazw claimow ("role", "sub") na
        // dlugie URI System.Security.Claims.ClaimTypes.* (zachowanie historyczne
        // JwtSecurityTokenHandler). Dzieki temu claim "role" zostaje "role" -- ale wtedy
        // RoleClaimType ponizej MUSI wskazywac na "role", inaczej [Authorize(Roles=...)]
        // i RequireRole(...) nigdy nie znajda roli (patrz pulapka w artykule).
        options.MapInboundClaims = false;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = JwtDemoSettings.Issuer,
            ValidateAudience = true,
            ValidAudience = JwtDemoSettings.Audience,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = JwtDemoSettings.SigningKey,
            ValidateLifetime = true,
            ClockSkew = TimeSpan.FromSeconds(5),
            RoleClaimType = "role",
            NameClaimType = "name",
        };
    });

builder.Services
    .AddAuthorizationBuilder()
    .AddPolicy("AdminOnly", policy => policy.RequireRole("admin"));

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/public/ping", () => Results.Ok(new { message = "pong", wymaga_tokenu = false }));

app.MapGet("/secure/profile", (ClaimsPrincipal user) => Results.Ok(new
{
    sub = user.FindFirstValue(JwtRegisteredClaimNames.Sub),
    name = user.Identity?.Name,
    role = user.FindAll("role").Select(c => c.Value).ToArray()
})).RequireAuthorization();

app.MapGet("/secure/admin-report", () => Results.Ok(new
{
    raport = "tylko dla administratorow: 42 tajne liczby"
})).RequireAuthorization("AdminOnly");

app.Run();

// Zabezpieczenie widocznosci niejawnej klasy Program dla WebApplicationFactory<Program> z
// osobnego projektu testow -- jak w wydaniach #5/#7, zostawione defensywnie mimo ze na tym
// SDK (10.0.400) okazalo sie zbedne.
public partial class Program { }
