import tensorflow
from tensorflow.keras import layers

#Tries to enable dynamic memory allocation on GPUs
try:
	for i in tensorflow.config.experimental.list_physical_devices("GPU"):
		tensorflow.config.experimental.set_memory_growth(i, True)
except:
	print("Device dynamic memory allocation failed!")

class PrunableDense(layers.Dense):
	"""
	Custom keras.layer class of a prunable Dense layer.
	"""
	def __init__(self, *args, **kwargs):
		super(PrunableDense, self).__init__(*args, **kwargs)
		self.trainable_channels = None
		self.trainable_bias = None
		self._kernel1 = None
		self._kernel2 = None
		self._bias1 = None
		self._bias2 = None
		self.saved_W = None
		self.saved_bias = None

	def build(self, input_shape):
		"""
		Custom build function that creates trainable channels Tensor and trainable bias Tensor.
		Parameters
		-------------
		input_shape: Shape of the layer input
		"""
		last_dim = input_shape[-1]
		self._kernel1 = self.add_weight("kernel1", shape=(last_dim, self.units), initializer=self.kernel_initializer, regularizer=self.kernel_regularizer, constraint=self.kernel_constraint, dtype=self.dtype, trainable=True)
		self._kernel2 = tensorflow.zeros((last_dim, self.units))
		self.trainable_channels = tensorflow.ones((last_dim, self.units), dtype=tensorflow.uint8)
		if self.use_bias:
			self._bias1 = self.add_weight("bias", shape=(self.units,), initializer=self.bias_initializer, regularizer=self.bias_regularizer, constraint=self.bias_constraint, dtype=self.dtype, trainable=True)
			self._bias2 = tensorflow.zeros((self.units,))
			self.trainable_bias = tensorflow.ones((self.units,), dtype=tensorflow.uint8)
		self.built = True

	@property
	def kernel(self):
		"""
		Custom kernel property that returns only trainable channels.
		"""
		t = tensorflow.cast(self.trainable_channels, dtype=self.dtype)
		return t * self._kernel1 + (1 - t) * self._kernel2

	@property
	def bias(self):
		"""
		Custom bias property that returns only trainable bias.
		"""
		if not self.use_bias:
			return None
		else:
			t = tensorflow.cast(self.trainable_bias, dtype=self.dtype)
			return t * self._bias1 + (1 - t) * self._bias2

	def save_kernel(self):
		self.saved_W = tensorflow.identity(self.kernel)

	def restore_kernel(self):
		self._kernel1.assign(self.saved_W)

	def save_bias(self):
		assert (self.use_bias)
		self.saved_bias = tensorflow.identity(self.bias)

	def restore_bias(self):
		assert (self.use_bias)
		self._bias1.assign(self.saved_bias)

	def prune_kernel(self, to_be_pruned):
		"""
		Prune the network layer on specific weights.
		Parameters
		---------------
		to_be_pruned: NumPy Array or Tensor of shape=kernel.shape with values in {0,  1} indicating which weights to keep (1) and which to drop (0).
		"""
		t = tensorflow.cast(to_be_pruned, dtype=tensorflow.float32)
		new_pruned = 1 - tensorflow.maximum((1 - t) - (1 - tensorflow.cast(self.trainable_channels, dtype=tensorflow.float32)), 0)
		new_pruned_weights = (1 - new_pruned) * self._kernel1
		self._kernel2 += new_pruned_weights
		self.trainable_channels *= tensorflow.cast(t, dtype=tensorflow.uint8)

	def prune_bias(self, to_be_pruned):
		"""
		Prune the bias on specific weights.
		Parameters
		--------------
		to_be_pruned: NumPy Array or Tensor with shape=kernel.shape with values in {0,  1} indicating which weights to keep (1) and which to drop (0).
		"""
		assert (self.use_bias)
		
		t = tensorflow.cast(to_be_pruned, dtype=tensorflow.float32)
		new_pruned = 1 - tensorflow.maximum((1 - t) - (1 - tensorflow.cast(self.trainable_bias, dtype=tensorflow.float32)), 0)
		new_pruned_bias = (1 - new_pruned) * self._bias1
		self._bias2 += new_pruned_bias
		self.trainable_bias *= tensorflow.cast(t, dtype=tensorflow.uint8)
