-- NexusTrace Database Schema & Seed Data (SIH26189 Prototype)
-- Database: crime_network_prototype

CREATE DATABASE IF NOT EXISTS `crime_network_prototype` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `crime_network_prototype`;

-- Drop tables if already present
DROP TABLE IF EXISTS `explanations`;
DROP TABLE IF EXISTS `relationships`;
DROP TABLE IF EXISTS `prison_visits`;
DROP TABLE IF EXISTS `financial_transactions`;
DROP TABLE IF EXISTS `cdr_records`;
DROP TABLE IF EXISTS `fir_records`;
DROP TABLE IF EXISTS `persons`;

-- 1. persons table
CREATE TABLE `persons` (
  `person_id` varchar(10) NOT NULL,
  `display_name` varchar(100) NOT NULL,
  `known_aliases` varchar(255) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `vehicle_number` varchar(20) DEFAULT NULL,
  `account_number` varchar(30) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `resolution_confidence` decimal(4,3) DEFAULT 1.000,
  PRIMARY KEY (`person_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 2. fir_records table
CREATE TABLE `fir_records` (
  `fir_id` varchar(20) NOT NULL,
  `case_id` varchar(20) NOT NULL,
  `filed_date` date NOT NULL,
  `narrative_text` text NOT NULL,
  `station` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`fir_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 3. cdr_records table
CREATE TABLE `cdr_records` (
  `cdr_id` varchar(20) NOT NULL,
  `caller_person_id` varchar(10) NOT NULL,
  `callee_person_id` varchar(10) NOT NULL,
  `call_datetime` datetime NOT NULL,
  `duration_seconds` int(11) DEFAULT NULL,
  PRIMARY KEY (`cdr_id`),
  KEY `caller_person_id` (`caller_person_id`),
  KEY `callee_person_id` (`callee_person_id`),
  CONSTRAINT `cdr_records_ibfk_1` FOREIGN KEY (`caller_person_id`) REFERENCES `persons` (`person_id`),
  CONSTRAINT `cdr_records_ibfk_2` FOREIGN KEY (`callee_person_id`) REFERENCES `persons` (`person_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 4. financial_transactions table
CREATE TABLE `financial_transactions` (
  `txn_id` varchar(20) NOT NULL,
  `sender_person_id` varchar(10) NOT NULL,
  `receiver_person_id` varchar(10) NOT NULL,
  `txn_datetime` datetime NOT NULL,
  `amount_inr` decimal(12,2) DEFAULT NULL,
  PRIMARY KEY (`txn_id`),
  KEY `sender_person_id` (`sender_person_id`),
  KEY `receiver_person_id` (`receiver_person_id`),
  CONSTRAINT `financial_transactions_ibfk_1` FOREIGN KEY (`sender_person_id`) REFERENCES `persons` (`person_id`),
  CONSTRAINT `financial_transactions_ibfk_2` FOREIGN KEY (`receiver_person_id`) REFERENCES `persons` (`person_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 5. prison_visits table
CREATE TABLE `prison_visits` (
  `visit_id` varchar(20) NOT NULL,
  `visitor_person_id` varchar(10) NOT NULL,
  `inmate_person_id` varchar(10) NOT NULL,
  `visit_date` date NOT NULL,
  `facility` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`visit_id`),
  KEY `visitor_person_id` (`visitor_person_id`),
  KEY `inmate_person_id` (`inmate_person_id`),
  CONSTRAINT `prison_visits_ibfk_1` FOREIGN KEY (`visitor_person_id`) REFERENCES `persons` (`person_id`),
  CONSTRAINT `prison_visits_ibfk_2` FOREIGN KEY (`inmate_person_id`) REFERENCES `persons` (`person_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 6. relationships table
CREATE TABLE `relationships` (
  `edge_id` int(11) NOT NULL AUTO_INCREMENT,
  `person_a_id` varchar(10) NOT NULL,
  `person_b_id` varchar(10) NOT NULL,
  `channel` enum('co_accused','call','transaction','prison_visit','ai_predicted') NOT NULL,
  `evidence_tier` enum('direct_evidence','corroborated_association','analytical_inference','ai_predicted_link') NOT NULL,
  `confidence_score` decimal(4,3) DEFAULT NULL,
  `source_record_id` varchar(20) DEFAULT NULL,
  `first_seen` datetime DEFAULT NULL,
  `last_seen` datetime DEFAULT NULL,
  `frequency` int(11) DEFAULT 1,
  PRIMARY KEY (`edge_id`),
  KEY `person_a_id` (`person_a_id`),
  KEY `person_b_id` (`person_b_id`),
  CONSTRAINT `relationships_ibfk_1` FOREIGN KEY (`person_a_id`) REFERENCES `persons` (`person_id`),
  CONSTRAINT `relationships_ibfk_2` FOREIGN KEY (`person_b_id`) REFERENCES `persons` (`person_id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 7. explanations table
CREATE TABLE `explanations` (
  `person_id` varchar(10) NOT NULL,
  `network_role` varchar(100) DEFAULT NULL,
  `priority` enum('LOW','MEDIUM','HIGH') DEFAULT 'MEDIUM',
  `confidence_pct` int(11) DEFAULT NULL,
  `explanation_text` text DEFAULT NULL,
  `generated_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`person_id`),
  CONSTRAINT `explanations_ibfk_1` FOREIGN KEY (`person_id`) REFERENCES `persons` (`person_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ==========================================
-- SEED DATA INSERTION
-- ==========================================

-- Persons seed data
INSERT INTO `persons` (`person_id`, `display_name`, `known_aliases`, `phone_number`, `vehicle_number`, `account_number`, `address`, `resolution_confidence`) VALUES
('P01', 'Arun Kumar S.', 'Arun K, A. Kumar', '9840011122', 'TN22AB1234', 'ACC10001', 'Perambur, Chennai', 1.000),
('P04', 'Rajesh Elumalai', 'Raja, R. Elumalai', '9840022233', 'TN10CD5678', 'ACC10004', 'Ambattur, Chennai', 1.000),
('P05', 'Suresh Babu', 'S. Babu', '9840033344', NULL, 'ACC10005', 'Guindy, Chennai', 1.000),
('P09', 'Vignesh Raja', 'Vicky, V. Raja', '9840044455', 'TN07EF4321', 'ACC10009', 'Tambaram, Chennai', 1.000),
('P17', 'Karthik Selvam', 'K. Selvam, Karthi', '9840055566', 'TN01GH8765', 'ACC10017', 'Anna Nagar, Chennai', 0.930),
('P22', 'Dinesh Prabhakaran', 'D. Prabhakaran', '9840066677', NULL, 'ACC10022', 'Velachery, Chennai', 1.000),
('P31', 'Manoj Iyappan', 'Manu, M. Iyappan', '9840077788', 'TN04IJ2468', 'ACC10031', 'Porur, Chennai', 1.000),
('P41', 'Bharath Venkatesan', 'B. Venkat', '9840088899', NULL, 'ACC10041', 'Adyar, Chennai', 1.000);

-- FIR Records seed data
INSERT INTO `fir_records` (`fir_id`, `case_id`, `filed_date`, `narrative_text`, `station`) VALUES
('FIR-2026-0298', '2026-CR-0298', '2026-06-03', 'FIR filed regarding an assault case at Tambaram. Vignesh Raja and Bharath Venkatesan are named as co-accused.', 'Tambaram PS'),
('FIR-2026-0417', '2026-CR-0417', '2026-08-12', 'Complainant reported a financial fraud syndicate operating from Anna Nagar. Preliminary investigation names Karthik Selvam and Rajesh Elumalai as co-accused in the case. Suresh Babu was named as a known associate of Karthik Selvam in witness statements.', 'Anna Nagar PS');

-- CDR Records seed data
INSERT INTO `cdr_records` (`cdr_id`, `caller_person_id`, `callee_person_id`, `call_datetime`, `duration_seconds`) VALUES
('CDR-0001', 'P17', 'P04', '2026-08-05 14:32:00', 180),
('CDR-0002', 'P17', 'P31', '2026-08-06 09:15:00', 320),
('CDR-0003', 'P17', 'P09', '2026-08-07 21:47:00', 95),
('CDR-0004', 'P17', 'P31', '2026-08-08 22:10:00', 410),
('CDR-0005', 'P17', 'P31', '2026-08-09 08:02:00', 260),
('CDR-0006', 'P31', 'P22', '2026-08-09 12:30:00', 140);

-- Financial Transactions seed data
INSERT INTO `financial_transactions` (`txn_id`, `sender_person_id`, `receiver_person_id`, `txn_datetime`, `amount_inr`) VALUES
('TXN-0001', 'P17', 'P09', '2026-08-04 10:00:00', 25000.00),
('TXN-0002', 'P09', 'P41', '2026-08-04 16:00:00', 25000.00),
('TXN-0003', 'P31', 'P22', '2026-08-09 13:00:00', 12000.00);

-- Prison Visits seed data
INSERT INTO `prison_visits` (`visit_id`, `visitor_person_id`, `inmate_person_id`, `visit_date`, `facility`) VALUES
('VIS-0001', 'P05', 'P41', '2026-07-20', 'Puzhal Central Prison');

-- Relationships seed data
INSERT INTO `relationships` (`edge_id`, `person_a_id`, `person_b_id`, `channel`, `evidence_tier`, `confidence_score`, `source_record_id`, `first_seen`, `last_seen`, `frequency`) VALUES
(1, 'P17', 'P04', 'co_accused', 'direct_evidence', NULL, 'FIR-2026-0417', '2026-08-12 00:00:00', '2026-08-12 00:00:00', 1),
(2, 'P09', 'P17', 'co_accused', 'direct_evidence', NULL, 'FIR-2026-0417', '2026-08-12 00:00:00', '2026-08-12 00:00:00', 1),
(3, 'P17', 'P31', 'call', 'corroborated_association', NULL, 'CDR-0004', '2026-08-05 00:00:00', '2026-08-09 00:00:00', 4),
(4, 'P09', 'P41', 'transaction', 'corroborated_association', NULL, 'TXN-0002', '2026-08-04 00:00:00', '2026-08-04 00:00:00', 1),
(5, 'P41', 'P05', 'prison_visit', 'analytical_inference', NULL, 'VIS-0001', '2026-07-20 00:00:00', '2026-07-20 00:00:00', 1),
(6, 'P31', 'P22', 'ai_predicted', 'ai_predicted_link', 0.820, 'CDR-0006', '2026-08-09 00:00:00', '2026-08-09 00:00:00', 1);

-- Explanations seed data
INSERT INTO `explanations` (`person_id`, `network_role`, `priority`, `confidence_pct`, `explanation_text`, `generated_at`) VALUES
('P17', 'Bridge / Coordinator candidate', 'HIGH', 82, 'P17 shows high betweenness centrality, sits on the shortest path between two otherwise separate clusters, and had a sharp rise in call frequency with P31 in the 72 hours before a related incident. This is an investigative lead — human verification required.', '2026-09-15 11:06:06');
