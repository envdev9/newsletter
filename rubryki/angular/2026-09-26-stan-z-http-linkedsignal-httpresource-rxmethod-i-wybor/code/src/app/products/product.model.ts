export interface Product {
  id: number;
  name: string;
  category: string;
  price: number;
}

export interface ProductDetails extends Product {
  description: string;
  stock: number;
}

export interface OrderResult {
  orderId: string;
}
