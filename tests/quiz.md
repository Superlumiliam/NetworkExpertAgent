### Question 1
igmpv3协议中，query interval字段默认值是多少？
### Expected Answer
根据RFC 3376 8.2节，Query Interval默认值是125秒。

### Question 2
OSPF Hello Packet中Network Mask字段的作用是什么？
### Expected Answer
根据RFC 2328，Network Mask字段包含了与该接口关联的子网掩码。

### Question 3
HTTP/2的Stream ID有什么规则？
### Expected Answer
根据RFC 7540，客户端发起的Stream ID必须是奇数，服务端发起的Stream ID必须是偶数。Stream 0用于连接控制消息。

### Question 4
IGMPv3协议中，组播组235.0.0.1的source是INCLUDE(10.0.0.1,10.0.0.2),此时收到igmp report报文为TO_EX(10.0.0.2,10.0.0.3),那么New Router State应该是什么？
### Expected Answer
根据rfc6.4.2节，新路由器状态为EXCLUDE(10.0.0.2,10.0.0.3)
