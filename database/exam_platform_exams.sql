CREATE DATABASE  IF NOT EXISTS `exam_platform` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `exam_platform`;
-- MySQL dump 10.13  Distrib 8.0.41, for Win64 (x86_64)
--
-- Host: localhost    Database: exam_platform
-- ------------------------------------------------------
-- Server version	8.0.41

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `exams`
--

DROP TABLE IF EXISTS `exams`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `exams` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `time_limit_minutes` int NOT NULL,
  `creator_id` int NOT NULL,
  `is_published` tinyint(1) DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `access_code` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allowed_ip_range` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `available_from` timestamp NULL DEFAULT NULL,
  `available_until` timestamp NULL DEFAULT NULL,
  `max_attempts` int DEFAULT '1',
  `join_before_minutes` int DEFAULT '15',
  `require_lockdown` tinyint(1) DEFAULT '1',
  `allow_calculator` tinyint(1) DEFAULT '0',
  `allow_scratch_pad` tinyint(1) DEFAULT '1',
  `randomize_questions` tinyint(1) DEFAULT '1',
  `one_question_at_time` tinyint(1) DEFAULT '0',
  `prevent_copy_paste` tinyint(1) DEFAULT '1',
  `require_webcam` tinyint(1) DEFAULT '0',
  `allow_backward_navigation` tinyint(1) DEFAULT '1',
  `show_remaining_time` tinyint(1) DEFAULT '1',
  `auto_submit` tinyint(1) DEFAULT '1',
  `require_face_verification` tinyint(1) DEFAULT '0',
  `proctor_monitoring` tinyint(1) DEFAULT '0',
  `monitor_screen_share` tinyint(1) DEFAULT '0',
  `periodic_checks` tinyint(1) DEFAULT '1',
  `detect_browser_exit` tinyint(1) DEFAULT '1',
  `max_warnings` int DEFAULT '3',
  `block_virtual_machines` tinyint(1) DEFAULT '1',
  `browser_fullscreen` tinyint(1) DEFAULT '1',
  `restrict_keyboard` tinyint(1) DEFAULT '0',
  `block_external_displays` tinyint(1) DEFAULT '1',
  `proctor_instructions` text COLLATE utf8mb4_unicode_ci,
  `proctor_notes` text COLLATE utf8mb4_unicode_ci,
  `max_students_per_proctor` int DEFAULT '20',
  `proctor_join_before` int DEFAULT '30',
  `group_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_creator_published` (`creator_id`,`is_published`),
  KEY `idx_access_time` (`available_from`,`available_until`),
  KEY `idx_created_at` (`created_at`),
  KEY `fk_exam_group` (`group_id`),
  CONSTRAINT `exams_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_exam_group` FOREIGN KEY (`group_id`) REFERENCES `groups` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `exams`
--

LOCK TABLES `exams` WRITE;
/*!40000 ALTER TABLE `exams` DISABLE KEYS */;
INSERT INTO `exams` VALUES (9,'test 1 ','hello ',5,2,1,'2025-05-21 11:38:37',NULL,NULL,NULL,NULL,1,15,1,0,1,1,0,1,0,1,1,1,0,0,0,1,1,3,1,1,0,1,NULL,NULL,20,30,1),(10,'hiq3rwedthgjkl','fuck you ',5,2,1,'2025-05-22 02:25:14',NULL,NULL,NULL,NULL,1,15,1,0,1,1,0,1,0,1,1,1,0,0,0,1,1,3,1,1,0,1,NULL,NULL,20,30,1),(11,'sdfghjk,l./kjhgfdfghjkl;\'','adfghjkl;\';lkjhgfghjkl;',5,2,1,'2025-05-22 03:07:07',NULL,NULL,NULL,NULL,1,15,1,0,1,1,0,1,0,1,1,1,0,0,0,1,1,3,1,1,0,1,NULL,NULL,20,30,1);
/*!40000 ALTER TABLE `exams` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-22 14:21:36
