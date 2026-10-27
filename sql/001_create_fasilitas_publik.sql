
-- AKHARI GeoLake
-- Migration 001: Fasilitas Publik

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS fasilitas_publik (
    id BIGSERIAL PRIMARY KEY,
    nama VARCHAR(150) NOT NULL,
    jenis VARCHAR(50) NOT NULL,
    desa VARCHAR(100),
    geom GEOMETRY(Point, 4326)
);
