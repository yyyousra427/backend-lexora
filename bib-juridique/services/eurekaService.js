const eurekaClient = require('../config/eureka');

const startEureka = () => {
  eurekaClient.start((error) => {
    if (error) {
      console.error('❌ Eureka registration failed:', error);
    } else {
      console.log('✅ Registered with Eureka successfully');
    }
  });
};

const stopEureka = () => {
  eurekaClient.stop();
  console.log('🛑 Eureka client stopped');
};

module.exports = { startEureka, stopEureka };
