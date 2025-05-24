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
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `message` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `related_id` int DEFAULT NULL,
  `is_read` tinyint(1) DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_read` (`user_id`,`is_read`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notifications`
--

LOCK TABLES `notifications` WRITE;
/*!40000 ALTER TABLE `notifications` DISABLE KEYS */;
INSERT INTO `notifications` VALUES (1,4,'Your Python Basics exam has been graded.','exam_graded',1,1,'2025-05-02 23:57:47'),(2,5,'Your Python Basics exam has been graded.','exam_graded',2,1,'2025-05-03 23:57:47'),(3,4,'Your Data Structures exam has been graded.','exam_graded',3,1,'2025-05-08 23:57:47'),(4,6,'Your Data Structures exam has been graded.','exam_graded',4,1,'2025-05-09 23:57:47'),(5,5,'Your Web Development exam has been graded.','exam_graded',5,1,'2025-05-12 23:57:47'),(6,4,'A new exam \"Advanced Python\" has been created.','exam_created',5,1,'2025-05-17 23:57:47'),(7,5,'A new exam \"Advanced Python\" has been created.','exam_created',5,0,'2025-05-17 23:57:47'),(8,6,'A new exam \"Advanced Python\" has been created.','exam_created',5,0,'2025-05-17 23:57:47'),(9,4,'New exam available: \'test 1 \'','new_exam',6,1,'2025-05-19 19:39:55'),(10,4,'New exam available: \'test tanush \'','new_exam',7,1,'2025-05-20 07:00:06'),(11,5,'New exam available: \'test tanush \'','new_exam',7,0,'2025-05-20 07:00:07'),(12,6,'New exam available: \'test tanush \'','new_exam',7,0,'2025-05-20 07:00:07'),(13,4,'New exam available: \'test \'','new_exam',8,1,'2025-05-20 23:16:57'),(14,5,'New exam available: \'test \'','new_exam',8,0,'2025-05-20 23:16:57'),(15,6,'New exam available: \'test \'','new_exam',8,0,'2025-05-20 23:16:57'),(16,4,'New exam available in Rao Class : \'test \'','new_exam',8,1,'2025-05-21 00:01:40'),(17,4,'New exam available: \'Python Basics\'','new_exam',1,1,'2025-05-21 10:37:23'),(18,5,'New exam available: \'Python Basics\'','new_exam',1,0,'2025-05-21 10:37:23'),(19,6,'New exam available: \'Python Basics\'','new_exam',1,0,'2025-05-21 10:37:23'),(20,4,'New exam available: \'test 1 \'','new_exam',9,1,'2025-05-21 12:24:40'),(21,5,'New exam available: \'test 1 \'','new_exam',9,0,'2025-05-21 12:24:40'),(22,6,'New exam available: \'test 1 \'','new_exam',9,0,'2025-05-21 12:24:40'),(23,5,'New exam available in Rao Class : \'test 1 \'','new_exam',9,0,'2025-05-22 01:55:18'),(24,4,'New exam available: \'hiq3rwedthgjkl\'','new_exam',10,0,'2025-05-22 02:25:33'),(25,5,'New exam available: \'hiq3rwedthgjkl\'','new_exam',10,0,'2025-05-22 02:25:33'),(26,6,'New exam available: \'hiq3rwedthgjkl\'','new_exam',10,0,'2025-05-22 02:25:33'),(27,4,'New exam available: \'sdfghjk,l./kjhgfdfghjkl;\'\'','new_exam',11,0,'2025-05-22 03:07:29'),(28,5,'New exam available: \'sdfghjk,l./kjhgfdfghjkl;\'\'','new_exam',11,0,'2025-05-22 03:07:29'),(29,6,'New exam available: \'sdfghjk,l./kjhgfdfghjkl;\'\'','new_exam',11,0,'2025-05-22 03:07:29');
/*!40000 ALTER TABLE `notifications` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-22 14:21:35
