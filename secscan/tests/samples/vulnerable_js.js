// 包含多种安全漏洞的JavaScript测试代码
// 此文件包含10种安全漏洞，用于验证扫描器的正则检测能力

// SC004 - 硬编码密钥
const API_KEY = "sk-1234567890abcdef";
var password = "admin123456";

// SC003 - XSS：innerHTML赋值用户输入
document.getElementById('output').innerHTML = userInput;

// SC003 - XSS：document.write
document.write(userInput);

// SC002 - 命令注入：child_process.exec + 用户输入拼接
const child_process = require('child_process');
child_process.exec("ping " + userHost, (error, stdout) => {});

// SC006 - 不安全的反序列化：eval
var result = eval(userInput);

// SC007 - 弱加密：MD5哈希
const crypto = require('crypto');
const hash = crypto.createHash('md5').update(password).digest('hex');

// SC010 - 不安全的随机数：Math.random()
var token = Math.random();

// SC009 - 信息泄露：console.log输出敏感信息
console.log("User password: " + password);

// SC001 - SQL注入：字符串拼接SQL语句
var query = "SELECT * FROM users WHERE id = " + userId;

// SC008 - SSRF：fetch + 用户可控URL
fetch(userUrl).then(r => r.json());

// SC005 - 路径遍历：fs.readFileSync + 路径拼接
const fs = require('fs');
var data = fs.readFileSync("/data/" + userFile);
