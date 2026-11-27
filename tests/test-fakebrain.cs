// test-fakebrain.cs — não ACP giả cho CI test S4 (build thành fakebrain.exe).
// Trả lời initialize + session/new đủ để bridge Push-Event "ready"; khi
// nhận session/prompt thì stream "pong:<user>" rồi stopReason — text chứa
// USERNAME của process con nên test verify được não chạy dưới troly-agent
// thật, không phải fallback quyền chủ.
using System;
using System.Text.RegularExpressions;

class P {
    static int Main() {
        var idRe = new Regex(@"""id""\s*:\s*(\d+)");
        string l;
        while ((l = Console.In.ReadLine()) != null) {
            var m = idRe.Match(l);
            string id = m.Success ? m.Groups[1].Value : "0";
            if (l.Contains("\"initialize\"")) {
                W("{\"jsonrpc\":\"2.0\",\"id\":" + id +
                  ",\"result\":{\"protocolVersion\":1}}");
            } else if (l.Contains("\"session/new\"")) {
                W("{\"jsonrpc\":\"2.0\",\"id\":" + id +
                  ",\"result\":{\"sessionId\":\"s1\"}}");
            } else if (l.Contains("\"session/prompt\"")) {
                W("{\"jsonrpc\":\"2.0\",\"method\":\"session/update\"," +
                  "\"params\":{\"sessionId\":\"s1\",\"update\":{" +
                  "\"sessionUpdate\":\"agent_message_chunk\",\"content\":" +
                  "{\"type\":\"text\",\"text\":\"pong:" +
                  Environment.UserName + "\"}}}}");
                W("{\"jsonrpc\":\"2.0\",\"id\":" + id +
                  ",\"result\":{\"stopReason\":\"end_turn\"}}");
            }
        }
        return 0;
    }
    static void W(string s) {
        Console.Out.WriteLine(s);
        Console.Out.Flush();
    }
}
