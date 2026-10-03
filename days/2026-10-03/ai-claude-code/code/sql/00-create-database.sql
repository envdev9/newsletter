-- Tworzy osobna baze demo, zeby nie kolidowac z innymi bazami na tym samym SQL Serverze.
IF DB_ID('PrasowkaAiPlanReview') IS NULL
    CREATE DATABASE PrasowkaAiPlanReview;
GO
