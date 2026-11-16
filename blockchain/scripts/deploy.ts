import "dotenv/config";
import { network } from "hardhat";

const { ethers } = await network.connect();

console.log("Deploying AdaptiveCryptoSecurity...");

const contract = await ethers.deployContract("AdaptiveCryptoSecurity");
await contract.waitForDeployment();

const contractAddress = await contract.getAddress();
console.log("AdaptiveCryptoSecurity deployed to:", contractAddress);

const attestorAddress = process.env.ATTESTOR_ADDRESS;
if (attestorAddress) {
  const tx = await contract.setPQAttestor(attestorAddress, true);
  await tx.wait();
  console.log("Registered PQ attestor:", attestorAddress);
} else {
  console.log("ATTESTOR_ADDRESS not set — skipping attestor registration.");
}