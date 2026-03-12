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
What is the purpose of the Identification field in IPv4 header?
### Expected Answer
According to RFC 791, the Identification field is used to aid in assembling the fragments of a datagram.
