-- ============================================================================
-- DATABASE SCHEMA: QR Code Based Luggage Tracking System for Airline Transport
-- Author: Solomon Victoria Awazi (FT22ACMP0117)
-- ============================================================================

CREATE DATABASE IF NOT EXISTS airline_luggage_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE airline_luggage_db;

-- Drop tables in reverse foreign-key order if re-initializing
DROP TABLE IF EXISTS Tracking;
DROP TABLE IF EXISTS Luggage;
DROP TABLE IF EXISTS Passengers;
DROP TABLE IF EXISTS Users;

-- 1. USERS TABLE (System Administrators & Airline Staff)
CREATE TABLE Users (
    User_ID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(50) NOT NULL UNIQUE,
    Email VARCHAR(100) NOT NULL UNIQUE,
    Password VARCHAR(255) NOT NULL,
    Role ENUM('Admin', 'Staff') NOT NULL DEFAULT 'Staff',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. PASSENGERS TABLE
CREATE TABLE Passengers (
    Passenger_ID INT AUTO_INCREMENT PRIMARY KEY,
    Full_Name VARCHAR(100) NOT NULL,
    Phone_Number VARCHAR(25) NOT NULL,
    Email VARCHAR(100) NOT NULL,
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. LUGGAGE TABLE
CREATE TABLE Luggage (
    Luggage_ID INT AUTO_INCREMENT PRIMARY KEY,
    Passenger_ID INT NOT NULL,
    Tracking_Code VARCHAR(30) NOT NULL UNIQUE,
    QR_Code VARCHAR(255) NOT NULL,
    Weight DECIMAL(5,2) DEFAULT 0.00,
    Destination VARCHAR(100) NOT NULL,
    Status VARCHAR(50) NOT NULL DEFAULT 'Registered',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_luggage_passenger FOREIGN KEY (Passenger_ID)
        REFERENCES Passengers(Passenger_ID) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. TRACKING TABLE (Chronological Checkpoint Logs)
CREATE TABLE Tracking (
    Tracking_ID INT AUTO_INCREMENT PRIMARY KEY,
    Luggage_ID INT NOT NULL,
    Location VARCHAR(100) NOT NULL,
    Scan_Time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status VARCHAR(50) NOT NULL,
    Updated_By VARCHAR(50) DEFAULT 'System',
    CONSTRAINT fk_tracking_luggage FOREIGN KEY (Luggage_ID)
        REFERENCES Luggage(Luggage_ID) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================================
-- SAMPLE DEMONSTRATION DATA
-- Note: Default passwords below are hashed using Werkzeug PBKDF2-SHA256
-- Admin login -> Username: admin     | Password: password123
-- Staff login -> Username: staff_abv | Password: password123
-- ============================================================================

INSERT INTO Users (Username, Email, Password, Role) VALUES
('admin', 'admin@skytrackair.com', 'pbkdf2:sha256:600000$8X9kLm2PqR7vTz1N$c6d63b6e2f0a5c8a3d9f1b4e7c2a8f5d0e3b6a9c1f4d7e2b5a8c0f3e6d9a2b5c', 'Admin'),
('staff_abv', 'staff.abv@skytrackair.com', 'pbkdf2:sha256:600000$8X9kLm2PqR7vTz1N$c6d63b6e2f0a5c8a3d9f1b4e7c2a8f5d0e3b6a9c1f4d7e2b5a8c0f3e6d9a2b5c', 'Staff');

INSERT INTO Passengers (Full_Name, Phone_Number, Email) VALUES
('Solomon Anna', '+2348012345678', 'solomonanna@gmail.com'),
('Haruna Murjanatu', '+2348098765432', 'harunamuranatu@gmail.com'),
('Sarka Wogan', '+2348055512345', 'sarkawogan@gmail.com');