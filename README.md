###Free SMDR daemon

####by Gabriele Tozzi <gabriele@tozzi.eu>, 2010-2011

This software starts a TCP server and listens for a SMDR stream. The received  
data is then written in raw format to a log file and also to a MySQL database.  

### Setup

---

Here is the SQL to create the table:

```
 CREATE TABLE `freesmdr` (
  `idfreesmdr` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `call_start` datetime DEFAULT NULL,
  `call_duration` time DEFAULT NULL,
  `ring_duration` time DEFAULT NULL,
  `caller` varchar(255) DEFAULT NULL,
  `direction` enum('I','O') DEFAULT NULL,
  `called_number` varchar(255) DEFAULT NULL,
  `dialled_number` varchar(255) DEFAULT NULL,
  `account` varchar(255) DEFAULT NULL,
  `is_internal` tinyint(1) DEFAULT NULL COMMENT '**BOOL**',
  `call_id` int(10) unsigned DEFAULT NULL,
  `continuation` tinyint(1) DEFAULT NULL COMMENT '**BOOL**',
  `paty1device` char(5) DEFAULT NULL,
  `party1name` varchar(255) DEFAULT NULL,
  `party2device` char(5) DEFAULT NULL,
  `party2name` varchar(255) DEFAULT NULL,
  `hold_time` time DEFAULT NULL,
  `park_time` time DEFAULT NULL,
  `authvalid` varchar(255) DEFAULT NULL,
  `authcode` varchar(255) DEFAULT NULL,
  `user_charged` varchar(255) DEFAULT NULL,
  `call_charge` varchar(255) DEFAULT NULL,
  `currency` varchar(255) DEFAULT NULL,
  `amount_change` varchar(255) DEFAULT NULL COMMENT 'Amount at last User Change',
  `call_units` varchar(255) DEFAULT NULL,
  `units_change` varchar(255) DEFAULT NULL COMMENT 'Units at last User Change',
  `cost_per_unit` varchar(255) DEFAULT NULL,
  `markup` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`idfreesmdr`),
  KEY `direction_idx` (`direction`),
  KEY `caller_idx` (`caller`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Freesmdr log table';
```
