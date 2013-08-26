import tornado.ioloop
import tornado.httpserver
import tornado.web
import tornado.websocket
import tornado.gen
from tornado.options import options, define, parse_command_line
import json

import tornadoredis

define('port', default=8888, help="Run on the given port", type=int)
define('channel', default='torpubsub', help="Redis pub/sub channel")


redis = tornadoredis.Client()
redis.connect()


class MessageHandler(tornado.web.RequestHandler):
	def get(self):
		user = self.get_argument('user')
		cmds = self.get_argument('cmds')

		print '%s >> %s' % (user, cmds)

		redis.publish(options.channel, json.dumps((user, cmds)))
		self.set_header('Content-Type', 'text/javascript')
		self.write('1')


class StreamHandler(tornado.websocket.WebSocketHandler):
	def __init__(self, *args, **kwargs):
		super(StreamHandler, self).__init__(*args, **kwargs)
		self.listen()

	@tornado.gen.engine
	def listen(self):
		self.user = self.get_argument('user')

		self.redis = tornadoredis.Client()
		self.redis.connect()

		yield tornado.gen.Task(self.redis.subscribe, options.channel)
		self.redis.listen(self.on_callback)

	def on_callback(self, msg):
		if msg.kind == 'message':
			self.write_message(str(msg.body))
		if msg.kind == 'disconnect':
			self.write_message('The connection terminated due to a Redis server error.')
			self.close()

	def on_message(self, cmds):
		print '%s >> %s' % (self.user, cmds)
		redis.publish(options.channel, json.dumps([self.user, cmds]))

	def on_close(self):
		if self.redis.subscribed:
			self.redis.unsubscribe(options.channel)
			self.redis.disconnect()

application = tornado.web.Application([
	(r'/send', MessageHandler),
	(r'/', StreamHandler),
])

if __name__ == '__main__':
	parse_command_line()
	http_server = tornado.httpserver.HTTPServer(application)
	http_server.listen(options.port)
	print 'Server running at 0.0.0.0:%s\nQuit with CONTROL-C' % options.port
	tornado.ioloop.IOLoop.instance().start()