import tornado.ioloop
import tornado.httpserver
import tornado.web
import tornado.websocket
import tornado.gen
from tornado.options import options, define, parse_command_line
import json

import tornadoredis

define('port', default=8888, help="Run on the given port", type=int)

define('rhost', default='127.0.0.1', help='Specify the Redis host name')
define('rport', default=6379, help='Specify the Redis daemon port', type=int)
define('rchnn', default='torpubsub', help="Pub/sub channel name")


redis = tornadoredis.Client(options.rhost, options.rport)
redis.connect()


class StreamHandler(tornado.websocket.WebSocketHandler):
	def __init__(self, *args, **kwargs):
		super(StreamHandler, self).__init__(*args, **kwargs)
		self.listen()

	@tornado.gen.engine
	def listen(self):
		self.user = self.get_argument('user')

		self.redis = tornadoredis.Client(options.rhost, options.rport)
		self.redis.connect()

		yield tornado.gen.Task(self.redis.subscribe, options.rchnn)
		self.redis.listen(self.on_callback)

	def on_callback(self, msg):
		if msg.kind == 'message':
			self.write_message(str(msg.body))
		if msg.kind == 'disconnect':
			self.write_message('The connection terminated due to a Redis server error.')
			self.close()

	def on_message(self, cmds):
		print '%s >> %s' % (self.user, cmds)
		redis.publish(options.rchnn, json.dumps([self.user, cmds]))

	def on_close(self):
		if self.redis.subscribed:
			self.redis.unsubscribe(options.rchnn)
			self.redis.disconnect()

app = tornado.web.Application([
	(r'/', StreamHandler),
])

if __name__ == '__main__':
	parse_command_line()
	http_server = tornado.httpserver.HTTPServer(app)
	http_server.listen(options.port)

	print 'Server running at 0.0.0.0:%s\nQuit with CONTROL-C' % options.port
	tornado.ioloop.IOLoop.instance().start()