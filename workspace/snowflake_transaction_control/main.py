from snowflake.snowflake import SnowflakeSession

class TransactionController:
    def __init__(self):
        self.session = SnowflakeSession()
        self.transaction_status = False

    def start_transaction(self):
        self.transaction_status = True
        self.session.connect()
        return self.transaction_status

    def end_transaction(self):
        self.transaction_status = False
        self.session.close()
        return self.transaction_status

if __name__ == '__main__':
    controller = TransactionController()
    print('Transaction status:', controller.transaction_status)